"""
brain dedup — Deduplicacao semantica para Brain chunks e insights.

Antes de inserir um novo chunk ou insight, verifica se ja existe um
semanticamente equivalente (similaridade > threshold via pgvector).
Se existir, incrementa confirmation_count no existente ao inves de duplicar.

Usa RPCs Supabase:
  - match_similar_chunks(query_embedding, similarity_threshold, match_count)
  - match_similar_insights(query_embedding, similarity_threshold, match_count)
"""
from __future__ import annotations

import asyncio
import logging

from runtime.db import supabase

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.92


async def check_duplicate_chunk(
    embedding: list[float],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict | None:
    """Retorna chunk mais similar se acima do threshold, None se e novo.

    Returns:
        dict com keys 'id' e 'similarity' do chunk existente, ou None.
    """
    if not embedding:
        return None

    try:
        result = await asyncio.to_thread(
            lambda: supabase.rpc(
                "match_similar_chunks",
                {
                    "query_embedding": embedding,
                    "similarity_threshold": threshold,
                    "match_count": 1,
                },
            ).execute()
        )
        if result.data and len(result.data) > 0:
            match = result.data[0]
            return {"id": match["id"], "similarity": match["similarity"]}
    except Exception as e:
        logger.warning("[brain/dedup] falha ao verificar duplicata chunk: %s", e)

    return None


async def check_duplicate_insight(
    embedding: list[float],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict | None:
    """Retorna insight mais similar se acima do threshold, None se e novo.

    Returns:
        dict com keys 'id' e 'similarity' do insight existente, ou None.
    """
    if not embedding:
        return None

    try:
        result = await asyncio.to_thread(
            lambda: supabase.rpc(
                "match_similar_insights",
                {
                    "query_embedding": embedding,
                    "similarity_threshold": threshold,
                    "match_count": 1,
                },
            ).execute()
        )
        if result.data and len(result.data) > 0:
            match = result.data[0]
            return {"id": match["id"], "similarity": match["similarity"]}
    except Exception as e:
        logger.warning("[brain/dedup] falha ao verificar duplicata insight: %s", e)

    return None


async def confirm_existing_chunk(chunk_id: str) -> None:
    """Incrementa confirmation_count no chunk existente (atomic via RPC)."""
    try:
        # P1-8: Atomic increment via RPC — no read-then-write race
        await asyncio.to_thread(
            lambda: supabase.rpc(
                "increment_confirmation_count",
                {"p_table": "brain_chunks", "p_id": chunk_id},
            ).execute()
        )
    except Exception as rpc_err:
        logger.warning("[brain/dedup] RPC increment failed for chunk %s, using fallback: %s", chunk_id, rpc_err)
        # Fallback: read-then-write (less safe but functional)
        try:
            current = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("confirmation_count")
                .eq("id", chunk_id)
                .single()
                .execute()
            )
            count = (current.data.get("confirmation_count") or 0) + 1
            await asyncio.to_thread(
                lambda c=count: supabase.table("brain_chunks")
                .update({"confirmation_count": c})
                .eq("id", chunk_id)
                .execute()
            )
        except Exception as e:
            logger.warning("[brain/dedup] fallback falha ao confirmar chunk %s: %s", chunk_id, e)


async def confirm_existing_insight(insight_id: str) -> None:
    """Incrementa confirmation_count no insight existente (atomic via RPC)."""
    try:
        # P1-8: Atomic increment via RPC — no read-then-write race
        await asyncio.to_thread(
            lambda: supabase.rpc(
                "increment_confirmation_count",
                {"p_table": "brain_insights", "p_id": insight_id},
            ).execute()
        )
    except Exception as rpc_err:
        logger.warning("[brain/dedup] RPC increment failed for insight %s, using fallback: %s", insight_id, rpc_err)
        # Fallback: read-then-write (less safe but functional)
        try:
            current = await asyncio.to_thread(
                lambda: supabase.table("brain_insights")
                .select("confirmation_count")
                .eq("id", insight_id)
                .single()
                .execute()
            )
            count = (current.data.get("confirmation_count") or 0) + 1
            await asyncio.to_thread(
                lambda c=count: supabase.table("brain_insights")
                .update({"confirmation_count": c})
                .eq("id", insight_id)
                .execute()
            )
        except Exception as e:
            logger.warning("[brain/dedup] fallback falha ao confirmar insight %s: %s", insight_id, e)
