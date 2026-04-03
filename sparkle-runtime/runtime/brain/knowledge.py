"""
runtime/brain/knowledge.py — Brain Knowledge Retriever.

Busca conhecimento estruturado do Brain para uso por qualquer handler.
Substitui a busca simples por chunks com busca em 3 niveis:

  Nivel 1: Sintese de dominio (brain_domain_syntheses) — visao consolidada
  Nivel 2: Insights relevantes (brain_insights) — tecnicas e frameworks especificos
  Nivel 3: Chunks crus (brain_chunks) — contexto bruto adicional

Resultado: um bloco de texto formatado pronto para injecao em prompt.
"""
from __future__ import annotations

import asyncio
import os

import httpx

from runtime.db import supabase


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


async def retrieve_knowledge(
    topic: str,
    domain_hint: str | None = None,
    insight_types: list[str] | None = None,
    client_id: str | None = None,
    max_insights: int = 6,
    max_chunks: int = 4,
    include_synthesis: bool = True,
) -> dict:
    """
    Busca conhecimento estruturado do Brain em 3 niveis.
    Retorna dict com:
      - context_text: bloco formatado para injecao em prompt
      - synthesis: dict da sintese do dominio (se existir)
      - insights: lista de insights relevantes
      - chunks: lista de chunks crus
      - domains_matched: dominios encontrados
    """
    embedding = await _get_embedding(topic)
    result: dict = {
        "context_text": "",
        "synthesis": None,
        "insights": [],
        "chunks": [],
        "domains_matched": [],
    }

    parts: list[str] = []

    # ── Nivel 1: Sintese de dominio ──
    if include_synthesis and embedding:
        try:
            syntheses = await asyncio.to_thread(
                lambda: supabase.rpc(
                    "match_domain_syntheses",
                    {"query_embedding": embedding, "match_count": 2},
                ).execute()
            )
            if syntheses.data:
                best = syntheses.data[0]
                result["synthesis"] = best
                result["domains_matched"].append(best["domain"])

                parts.append(f"=== CONHECIMENTO DO BRAIN: {best['domain'].upper()} ===")
                parts.append(f"(Sintese cruzada de {best.get('source_count', '?')} fontes)\n")
                parts.append(best.get("summary", ""))

                frameworks = best.get("key_frameworks") or []
                if frameworks:
                    parts.append("\nFRAMEWORKS RELEVANTES:")
                    for fw in frameworks[:3]:
                        parts.append(f"- {fw.get('title', '')}: {fw.get('description', '')}")

                techniques = best.get("key_techniques") or []
                if techniques:
                    parts.append("\nTECNICAS APLICAVEIS:")
                    for tc in techniques[:3]:
                        app = f" | Como usar: {tc['application']}" if tc.get("application") else ""
                        parts.append(f"- {tc.get('title', '')}: {tc.get('description', '')}{app}")

                conflicts = best.get("conflicts") or []
                if conflicts:
                    parts.append("\nPONTOS DE ATENCAO (fontes divergem):")
                    for cf in conflicts[:2]:
                        parts.append(
                            f"- {cf.get('topic', '')}: {cf.get('position_a', '')} vs {cf.get('position_b', '')}"
                        )
        except Exception as e:
            print(f"[knowledge] sintese lookup falhou: {e}")

    # ── Nivel 2: Insights especificos ──
    if embedding:
        try:
            insight_params: dict = {
                "query_embedding": embedding,
                "match_count": max_insights,
            }
            if insight_types:
                insight_params["type_filter"] = insight_types

            insights_result = await asyncio.to_thread(
                lambda: supabase.rpc("match_brain_insights", insight_params).execute()
            )
            insights = insights_result.data or []
            result["insights"] = insights

            # Filtra insights nao cobertos pela sintese
            synthesis_domains = set(result["domains_matched"])
            novel_insights = [
                i for i in insights
                if i.get("domain") not in synthesis_domains or i.get("similarity", 0) > 0.85
            ]

            if novel_insights:
                parts.append("\n=== INSIGHTS ADICIONAIS ===")
                for ins in novel_insights[:4]:
                    parts.append(f"[{ins.get('insight_type', 'insight').upper()}] {ins.get('title', '')}")
                    parts.append(f"  {ins.get('content', '')}")
                    if ins.get("application"):
                        parts.append(f"  Como usar: {ins['application']}")
        except Exception as e:
            print(f"[knowledge] insights lookup falhou: {e}")

    # ── Nivel 3: Chunks crus (complemento) ──
    if embedding:
        try:
            chunks_result = await asyncio.to_thread(
                lambda: supabase.rpc(
                    "match_brain_chunks",
                    {
                        "query_embedding": embedding,
                        "pipeline_type_in": "especialista",
                        "client_id_in": None,
                        "match_count": max_chunks,
                    },
                ).execute()
            )
            chunks = chunks_result.data or []
            result["chunks"] = chunks

            # So inclui chunks se nao achou sintese nem insights
            if chunks and not parts:
                parts.append("\n=== CONTEXTO DO BRAIN ===")
                for c in chunks[:3]:
                    text = c.get("canonical_text") or c.get("raw_content", "")
                    parts.append(text[:300])
        except Exception as e:
            print(f"[knowledge] chunks lookup falhou: {e}")

    result["context_text"] = "\n".join(parts)
    return result
