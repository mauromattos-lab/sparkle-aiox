"""
C2-B3: Namespace context injection utility.

Reusable function that queries a specific Brain namespace and returns
formatted context ready for injection into LLM prompts.

Usage:
    context = await fetch_namespace_context('mauro-personal', 'qual a visao de longo prazo?')
    # Returns: "[CONTEXTO BRAIN -- mauro-personal]\n...chunks...\n[/CONTEXTO BRAIN]"
    # Returns: "" if no results or on error (graceful degradation)
"""
from __future__ import annotations

import asyncio
import logging
import time

from runtime.brain.embedding import get_embedding
from runtime.db import supabase

logger = logging.getLogger(__name__)


async def fetch_namespace_context(
    namespace: str,
    query: str,
    max_tokens: int = 2000,
) -> str:
    """
    Query a specific Brain namespace and return formatted context for prompt injection.

    Args:
        namespace: Brain namespace to query (e.g. 'mauro-personal', 'sparkle-ops', 'sparkle-lore')
        query: The search query (user message, task description, etc.)
        max_tokens: Approximate token budget (chars / 4). Truncates keeping highest-similarity chunks.

    Returns:
        Formatted context block string, or empty string if no results / on error.
    """
    if not namespace or not query:
        return ""

    start_ms = time.monotonic()
    try:
        chunks = await _search_namespace(namespace, query)

        if not chunks:
            elapsed = _elapsed_ms(start_ms)
            logger.info(
                "[namespace_context] namespace=%s query=%s chunks=0 latency_ms=%.0f",
                namespace, query[:80], elapsed,
            )
            return ""

        # Sort by similarity descending (highest first) so truncation drops lowest
        chunks.sort(key=lambda c: c.get("similarity", 0), reverse=True)

        # Format and truncate to max_tokens budget
        formatted = _format_and_truncate(namespace, chunks, max_tokens)

        elapsed = _elapsed_ms(start_ms)
        logger.info(
            "[namespace_context] namespace=%s query=%s chunks=%d latency_ms=%.0f",
            namespace, query[:80], len(chunks), elapsed,
        )

        return formatted

    except Exception as e:
        elapsed = _elapsed_ms(start_ms)
        logger.error(
            "[namespace_context] FAILED namespace=%s query=%s error=%s latency_ms=%.0f",
            namespace, query[:80], e, elapsed,
        )
        # Graceful degradation: never break the caller
        return ""


# -- Internal helpers ----------------------------------------------------------


async def _search_namespace(namespace: str, query: str) -> list[dict]:
    """
    Vector search in a specific brain namespace, with text search fallback.
    Reuses the same patterns as brain_query handler but scoped to namespace.
    """
    # Try vector search first
    try:
        embedding = await get_embedding(query)
        if embedding:
            rpc_params = {
                "query_embedding": embedding,
                "pipeline_type_in": "mauro",
                "client_id_in": None,
                "match_count": 6,
                "brain_owner_in": namespace,
            }
            rpc_result = await asyncio.to_thread(
                lambda: supabase.rpc("match_brain_chunks", rpc_params).execute()
            )
            results = rpc_result.data or []

            # Client-side safety filter (in case RPC ignores brain_owner_in)
            results = [
                r for r in results
                if r.get("brain_owner") == namespace
                or r.get("brain_owner") is None  # legacy rows
            ]

            # Exclude rejected chunks
            results = [
                r for r in results
                if r.get("curation_status", "pending") != "rejected"
            ]

            if results:
                return results
    except Exception as e:
        logger.warning("[namespace_context] vector search failed, trying text fallback: %s", e)

    # Fallback: text search scoped to namespace
    return await _text_search_namespace(namespace, query)


async def _text_search_namespace(namespace: str, query: str) -> list[dict]:
    """Full-text search fallback scoped to a brain namespace."""
    words = [w for w in query.split() if len(w) > 3][:3]
    if not words:
        words = query.split()[:2]

    search_term = " | ".join(words)

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("knowledge_base")
            .select("id,type,content,source,client_id")
            .eq("brain_owner", namespace)
            .text_search("content", search_term)
            .limit(6)
            .execute()
        )
        return result.data or []
    except Exception:
        try:
            first_word = words[0] if words else query[:20]
            result = await asyncio.to_thread(
                lambda: supabase.table("knowledge_base")
                .select("id,type,content,source,client_id")
                .eq("brain_owner", namespace)
                .ilike("content", f"%{first_word}%")
                .limit(6)
                .execute()
            )
            return result.data or []
        except Exception as e2:
            logger.error("[namespace_context] text search failed: %s", e2)
            return []


def _format_and_truncate(namespace: str, chunks: list[dict], max_tokens: int) -> str:
    """
    Format chunks into a delimited block and truncate to max_tokens budget.
    Chunks must already be sorted by similarity (highest first).
    max_tokens is approximate: chars / 4.
    """
    max_chars = max_tokens * 4
    header = f"[CONTEXTO BRAIN -- {namespace}]"
    footer = f"[/CONTEXTO BRAIN]"

    # Reserve space for header + footer + newlines
    overhead = len(header) + len(footer) + 4  # 4 for \n chars
    budget = max_chars - overhead

    if budget <= 0:
        return ""

    lines = []
    used = 0
    for i, chunk in enumerate(chunks, 1):
        content = (
            chunk.get("raw_content")
            or chunk.get("content")
            or ""
        )[:800]
        source = chunk.get("source") or chunk.get("source_title") or ""
        tipo = chunk.get("type") or chunk.get("source_type") or "info"
        source_info = f" (fonte: {source})" if source else ""
        line = f"[{i}] [{tipo}]{source_info}\n{content}"

        if used + len(line) + 4 > budget:  # +4 for separator
            break
        lines.append(line)
        used += len(line) + 4

    if not lines:
        return ""

    body = "\n\n---\n\n".join(lines)
    return f"{header}\n{body}\n{footer}"


def _elapsed_ms(start: float) -> float:
    return (time.monotonic() - start) * 1000
