"""
Embedding provider abstraction — S8-P3.

Hoje: OpenAI text-embedding-3-small (1536 dims, $0.02/1M tokens).
Futuro: trocar o provider aqui, sem mudar brain_ingest ou brain_query.

Dimensions: 1536 (text-embedding-3-small default)

Feature flag: BRAIN_EMBEDDINGS_ENABLED (default: false)
  → false: generate_embedding sempre retorna None (seguro para produção sem OPENAI_API_KEY)
  → true: tenta gerar embedding, falha silenciosa se API indisponível
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536  # padrão do modelo


def _embeddings_enabled() -> bool:
    """Verifica se embeddings estão habilitados via env var."""
    return os.getenv("BRAIN_EMBEDDINGS_ENABLED", "false").lower() in ("true", "1", "yes")


async def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Gera embedding via OpenAI text-embedding-3-small.

    Returns:
        Lista de floats (1536 dims) ou None se:
        - BRAIN_EMBEDDINGS_ENABLED=false (feature desabilitada)
        - OPENAI_API_KEY não configurada
        - API OpenAI falhar (timeout, HTTP error, etc.)

    Note:
        Falha silenciosa intencional — brain_ingest salva o registro sem embedding
        em vez de falhar a ingestão inteira. Log de WARNING é emitido.
    """
    if not _embeddings_enabled():
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[embeddings] WARNING: OPENAI_API_KEY não configurada — embedding não gerado")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text[:8000],  # limite seguro de tokens para o modelo
                },
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data["data"][0]["embedding"]
            print(f"[embeddings] embedding gerado — {len(embedding)} dims, modelo={EMBEDDING_MODEL}")
            return embedding
    except httpx.TimeoutException:
        print("[embeddings] WARNING: timeout na API OpenAI — embedding não gerado")
        return None
    except httpx.HTTPStatusError as e:
        print(f"[embeddings] WARNING: HTTP {e.response.status_code} da OpenAI — embedding não gerado")
        return None
    except Exception as e:
        print(f"[embeddings] WARNING: erro inesperado ao gerar embedding: {e}")
        return None


async def estimate_cost_usd(total_chars: int) -> float:
    """
    Estima custo em USD para embeddings.
    text-embedding-3-small: $0.02 / 1M tokens.
    Aproximação: 1 token ≈ 4 chars.
    """
    estimated_tokens = total_chars / 4
    cost = (estimated_tokens / 1_000_000) * 0.02
    return round(cost, 6)
