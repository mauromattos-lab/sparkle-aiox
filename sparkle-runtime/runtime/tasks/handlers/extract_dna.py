"""
extract_dna handler — S9-P2D: DNA Extraction Pipeline.

Extrai DNA dos agentes a partir do corpus de chunks no Brain.
Cada chunk é classificado em 6 camadas via Claude Haiku:
  filosofia | modelo_mental | heuristica | framework | metodologia | dilema

Fluxo:
  1. Busca chunks do namespace em brain_chunks
  2. Haiku classifica cada chunk → camada + conteúdo extraído
  3. Insere em agent_dna com embedding
  4. Retorna estatísticas: {processed, inserted, cost_usd, layers_distribution}

Custo estimado: ~$0.40 para 200 chunks via Haiku ($0.002/1k tokens input)
dry_run=true: classifica sem inserir — para validação antes do commit.
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


_DNA_CLASSIFY_SYSTEM = """Você é um extrator de DNA cognitivo.

Dado um trecho de texto, determine se ele contém conhecimento relevante para uma das 6 camadas de DNA de agente:

CAMADAS:
- filosofia: crença fundamental, valor inegociável, princípio de vida ou negócio
- modelo_mental: forma de ver o mundo, analogia estrutural, lens para interpretar situações
- heuristica: regra prática, atalho de decisão ("quando X, sempre faça Y")
- framework: processo estruturado, metodologia, sequência de etapas
- metodologia: abordagem de trabalho, forma de executar, estilo operacional
- dilema: tensão irresolvida, trade-off recorrente, conflito entre dois valores legítimos

Se o trecho contém conteúdo relevante para UMA das camadas, retorne:
{"layer": "<camada>", "content": "<conteúdo extraído em 1-3 frases diretas>", "relevant": true}

Se o trecho não contém DNA relevante (é output técnico, dado operacional, status):
{"layer": null, "content": null, "relevant": false}

IMPORTANTE:
- O conteúdo extraído deve ser instrução de raciocínio, não descrição
- NÃO: "Mauro acredita que preço reflete valor"
- SIM: "Antes de responder sobre pricing: preço é declaração de valor, não cálculo de custo"
- Responda APENAS com JSON válido, sem markdown"""


async def _classify_chunk_dna(chunk_content: str, task_id: str | None) -> dict | None:
    """Classifica um chunk em uma camada de DNA. Retorna None se não relevante."""
    try:
        raw = await call_claude(
            prompt=f"Trecho para análise:\n\n{chunk_content[:1500]}",
            system=_DNA_CLASSIFY_SYSTEM,
            model="claude-haiku-4-5-20251001",
            client_id=settings.sparkle_internal_client_id,
            task_id=task_id,
            agent_id="brain",
            purpose="extract_dna",
            max_tokens=300,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = [l for l in cleaned.splitlines() if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
        if parsed.get("relevant") and parsed.get("layer") and parsed.get("content"):
            return parsed
        return None
    except Exception as e:
        print(f"[extract_dna] classify falhou: {e}")
        return None


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


async def handle_extract_dna(task: dict) -> dict:
    """
    Extrai DNA do corpus do Brain e popula a tabela agent_dna.
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    namespace = payload.get("namespace") or settings.sparkle_internal_client_id
    target_agent_id = payload.get("target_agent_id", "friday")
    dry_run = payload.get("dry_run", False)
    source_chunk_ids = payload.get("source_chunk_ids")  # lista opcional de UUIDs

    # Busca chunks
    try:
        # schema produção: raw_content, client_id é UUID (NULL para sparkle-internal)
        query = supabase.table("brain_chunks").select("id,raw_content,canonical_content")
        if source_chunk_ids:
            query = query.in_("id", source_chunk_ids)
        else:
            # sparkle-internal chunks têm client_id=NULL no schema produção
            query = query.is_("client_id", "null")

        result = await asyncio.to_thread(lambda: query.limit(300).execute())
        chunks = result.data or []
    except Exception as e:
        return {"error": f"Falha ao buscar chunks: {e}"}

    if not chunks:
        return {"message": f"Nenhum chunk encontrado para namespace={namespace}"}

    processed = 0
    inserted = 0
    layers_distribution: dict[str, int] = {}

    for chunk in chunks:
        processed += 1
        text = chunk.get("canonical_content") or chunk.get("raw_content", "")
        dna = await _classify_chunk_dna(text, task_id)

        if not dna:
            continue

        layer = dna["layer"]
        content = dna["content"]
        layers_distribution[layer] = layers_distribution.get(layer, 0) + 1

        if dry_run:
            inserted += 1
            continue

        # Gera embedding do conteúdo extraído
        embedding = await _get_embedding(content)

        row: dict = {
            "agent_id": target_agent_id,
            "layer": layer,
            "content": content,
            "source_chunk_id": chunk["id"],
            "active": True,
        }
        if embedding:
            row["embedding"] = embedding

        try:
            await asyncio.to_thread(
                lambda: supabase.table("agent_dna").insert(row).execute()
            )
            inserted += 1
        except Exception as e:
            print(f"[extract_dna] falha ao inserir dna row: {e}")

    return {
        "message": (
            f"{'[DRY RUN] ' if dry_run else ''}DNA extraction concluída.\n"
            f"Chunks processados: {processed}\n"
            f"Registros {'identificados' if dry_run else 'inseridos'}: {inserted}\n"
            f"Distribuição: {layers_distribution}"
        ),
        "processed": processed,
        "inserted": inserted,
        "dry_run": dry_run,
        "layers_distribution": layers_distribution,
        "agent_id": target_agent_id,
        "namespace": namespace,
    }
