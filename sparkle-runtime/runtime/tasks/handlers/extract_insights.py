"""
extract_insights handler — Fase 5 evoluida do Brain Pipeline.

Extrai insights acionaveis (frameworks, tecnicas, principios) de chunks do Brain.
Diferente do extract_dna (que extrai DNA de agente), aqui o foco e
conhecimento APLICAVEL — o que o sistema pode USAR ao criar/decidir/analisar.

Fluxo:
  1. Recebe chunk_ids (da pipeline) ou busca chunks sem insight extraido
  2. Haiku analisa cada chunk e extrai 0-3 insights tipados
  3. Gera embedding de cada insight
  4. Insere em brain_insights com rastreabilidade
  5. Atualiza brain_chunks.processed_stages += ['insight_extraction']
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


_INSIGHT_EXTRACT_SYSTEM = """Voce e um extrator de conhecimento acionavel.

Dado um trecho de conteudo educacional, tecnico ou estrategico, extraia INSIGHTS ACIONAVEIS.

Para cada insight encontrado, retorne:
{
  "insights": [
    {
      "domain": "<dominio do conhecimento>",
      "insight_type": "framework | tecnica | principio | metrica | processo | heuristica",
      "title": "<nome curto e memoravel, com atribuicao de fonte se possivel>",
      "content": "<descricao objetiva do insight em 2-5 frases>",
      "application": "<COMO usar na pratica — situacao concreta onde aplicar>",
      "tags": ["tag1", "tag2"],
      "confidence": 0.0-1.0
    }
  ]
}

REGRAS:
- Se o trecho nao contem insight acionavel (e apenas contexto, intro, transicao), retorne {"insights": []}
- "content" deve ser instrucao, nao descricao. NAO: "Hannah fala sobre CTAs". SIM: "Nunca coloque CTA como comando direto — embuta no fluxo narrativo"
- "application" e a parte mais importante: diz QUANDO e COMO usar
- Maximo 3 insights por trecho. Menos e melhor se forem mais densos.
- confidence: 0.9+ para afirmacao clara e atribuivel, 0.7 para inferencia, 0.5 para fragmento ambiguo
- Responda APENAS com JSON valido, sem markdown"""


async def _get_embedding(text: str) -> list[float] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": text[:8000]},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception:
        return None


def _clean_json(text: str) -> str:
    """Remove markdown code fences and fix truncated JSON from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Fix truncated JSON: try closing open brackets
    if text and not text.endswith("}"):
        text = text.rstrip(",\n ")
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")
        text += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
    return text.strip()


async def handle_extract_insights(task: dict) -> dict:
    """
    Extrai insights acionaveis de chunks do Brain.
    Payload:
      - source_chunk_ids: lista de UUIDs (da pipeline)
      - source_raw_ingestion_id: UUID da ingestao raw (rastreabilidade)
      - min_confidence: float (default 0.6) — filtra insights fracos
      - dry_run: bool — classifica sem inserir
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    client_id = task.get("client_id")
    source_chunk_ids = payload.get("source_chunk_ids")
    source_raw_ingestion_id = payload.get("source_raw_ingestion_id")
    min_confidence = payload.get("min_confidence", 0.6)
    dry_run = payload.get("dry_run", False)

    # 1. Busca chunks
    if source_chunk_ids:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id,raw_content,canonical_content,source_title,chunk_metadata,processed_stages")
            .in_("id", source_chunk_ids)
            .execute()
        )
    else:
        # fallback: chunks recentes sem insight extraido
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id,raw_content,canonical_content,source_title,chunk_metadata,processed_stages")
            .limit(100)
            .execute()
        )

    all_chunks = result.data or []
    # Filtra chunks que ja passaram por insight_extraction (se nao veio da pipeline)
    if not source_chunk_ids:
        all_chunks = [
            c for c in all_chunks
            if "insight_extraction" not in (c.get("processed_stages") or [])
        ]

    processed = 0
    inserted = 0
    domain_distribution: dict[str, int] = {}

    for chunk in all_chunks:
        processed += 1
        text = chunk.get("canonical_content") or chunk.get("raw_content", "")
        if not text or len(text) < 30:
            continue

        # 2. Haiku extrai insights
        try:
            raw_response = await call_claude(
                prompt=f"Trecho para analise:\n\n{text[:2000]}",
                system=_INSIGHT_EXTRACT_SYSTEM,
                model="claude-haiku-4-5-20251001",
                client_id=client_id or settings.sparkle_internal_client_id,
                task_id=task_id,
                agent_id="brain",
                purpose="extract_insights",
                max_tokens=1000,
            )
        except Exception as e:
            print(f"[extract_insights] Haiku falhou para chunk {chunk['id']}: {e}")
            continue

        try:
            cleaned = _clean_json(raw_response)
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"[extract_insights] JSON invalido para chunk {chunk['id']}: {raw_response[:200]}")
            continue

        insights = parsed.get("insights", [])

        for insight in insights:
            if insight.get("confidence", 0) < min_confidence:
                continue

            domain = (insight.get("domain") or "geral").lower().strip()
            domain_distribution[domain] = domain_distribution.get(domain, 0) + 1

            if dry_run:
                inserted += 1
                continue

            # 3. Embedding do insight
            embed_text = f"{insight.get('title', '')}: {insight.get('content', '')}. Aplicacao: {insight.get('application', '')}"
            embedding = await _get_embedding(embed_text)

            # 4. Insere em brain_insights
            row: dict = {
                "domain": domain,
                "insight_type": insight.get("insight_type", "heuristica"),
                "title": insight.get("title", ""),
                "content": insight.get("content", ""),
                "application": insight.get("application"),
                "source_attribution": chunk.get("source_title", ""),
                "source_chunk_ids": [str(chunk["id"])],
                "source_raw_ingestion_id": source_raw_ingestion_id,
                "confidence": insight.get("confidence", 0.8),
                "tags": insight.get("tags", []),
                "pipeline_type": "especialista",
            }
            if client_id and client_id != settings.sparkle_internal_client_id:
                row["client_id"] = client_id
            if embedding:
                row["embedding"] = embedding

            try:
                await asyncio.to_thread(
                    lambda r=row: supabase.table("brain_insights").insert(r).execute()
                )
                inserted += 1
            except Exception as e:
                print(f"[extract_insights] falha ao inserir insight: {e}")

        # 5. Marca chunk como processado
        if not dry_run:
            existing_stages = chunk.get("processed_stages") or []
            if "insight_extraction" not in existing_stages:
                try:
                    await asyncio.to_thread(
                        lambda cid=chunk["id"], stages=existing_stages: supabase.table("brain_chunks")
                        .update({"processed_stages": stages + ["insight_extraction"]})
                        .eq("id", cid)
                        .execute()
                    )
                except Exception as e:
                    print(f"[extract_insights] falha ao marcar chunk {chunk['id']}: {e}")

    return {
        "message": (
            f"{'[DRY RUN] ' if dry_run else ''}Insight Extraction concluida. "
            f"Chunks: {processed}, Insights: {inserted}, Dominios: {domain_distribution}"
        ),
        "processed": processed,
        "inserted": inserted,
        "dry_run": dry_run,
        "domain_distribution": domain_distribution,
    }
