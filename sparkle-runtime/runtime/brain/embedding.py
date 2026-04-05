"""
runtime/brain/embedding.py — Centralized embedding generation.

Single source of truth for OpenAI embedding calls across the entire runtime.
All modules that need embeddings import from here instead of maintaining
their own copy. (P1-3 fix: deduplicated _get_embedding)

Uses a shared httpx.AsyncClient for connection pooling — avoids opening
a new TCP connection per embedding request during batch ingestion.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_MODEL = "text-embedding-3-small"
_MAX_INPUT_CHARS = 8000
_TIMEOUT = 10.0

# Shared client — created lazily, reused across calls for connection pooling.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _client


async def get_embedding(text: str) -> list[float] | None:
    """Generate an embedding vector via OpenAI text-embedding-3-small.

    Returns None when:
      - OPENAI_API_KEY is not set
      - The API call fails for any reason

    The input is truncated to 8000 chars to stay within model limits.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = _get_client()
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": _MODEL, "input": text[:_MAX_INPUT_CHARS]},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as e:
        logger.warning("[brain/embedding] embedding failed: %s", e)
        return None
