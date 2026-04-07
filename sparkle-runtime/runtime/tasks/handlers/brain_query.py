"""
brain_query handler — Brain Fase A.

"Brain, o que você sabe sobre YouTube?"

Fluxo:
  1. Extrai a query do payload
  2. Busca no knowledge_base (text search + fallback para vector via match_brain_chunks)
  3. Claude Haiku sintetiza os resultados
  4. Retorna resposta para Friday → Mauro via WhatsApp

Day 1-7 do 30 Day Proof: provar que o Brain existe como ativo consultável.
"""
from __future__ import annotations

import asyncio
import os

import httpx

from runtime.brain.isolation import get_brain_owner_filter
from runtime.brain.usage import track_chunk_usage
from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

_BRAIN_SYSTEM = """Você é o Brain da Sparkle AIOX — a memória coletiva de toda a operação.
Mauro perguntou sobre um tema. Você recebeu trechos relevantes da base de conhecimento.
Sintetize o que você sabe de forma direta, útil e honesta.

Regras:
- Se há informação relevante, entregue o essencial em até 5 bullet points ou 3 parágrafos curtos
- Se a informação for parcial, diga o que sabe e sinalize o que está faltando
- Se não houver nada relevante, diga claramente: "Brain ainda não tem conhecimento sobre esse tema"
- Nunca invente. Use apenas o que está nos trechos fornecidos.
- Tom: direto, sem enrolação. Você é um sistema, não um coach motivacional."""


async def handle_brain_query(task: dict) -> dict:
    """
    Consulta o Brain sobre um tema.
    Retorna {"message": "<resposta sintetizada>"}.
    """
    payload = task.get("payload", {})
    query = payload.get("query") or payload.get("original_text", "")

    if not query:
        return {"message": "Brain: nenhuma query recebida. Como posso ajudar?"}

    task_id = task.get("id")

    # B1-03: Brain isolation — resolve brain_owner filter for this agent
    agent_slug = task.get("agent_id") or payload.get("agent_slug", "friday")
    client_id = task.get("client_id") or payload.get("client_id")
    brain_owner = get_brain_owner_filter(agent_slug, client_id)

    chunks = await _search_knowledge_base(query, brain_owner=brain_owner)

    # B3-05: Track usage for returned chunks (fire-and-forget)
    if chunks:
        chunk_ids = [c.get("id") for c in chunks if c.get("id")]
        if chunk_ids:
            asyncio.ensure_future(track_chunk_usage(chunk_ids))

    if not chunks:
        return {
            "message": (
                f"Brain: ainda não tenho conhecimento registrado sobre '{query}'. "
                "Você pode alimentar o Brain com notas, documentos ou conversas — "
                "e na próxima consulta eu já saberei."
            )
        }

    context = _format_chunks(chunks)

    prompt = (
        f"Pergunta do Mauro: {query}\n\n"
        f"Trechos do Brain:\n{context}"
    )

    response = await call_claude(
        prompt=prompt,
        system=_BRAIN_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=settings.sparkle_internal_client_id,
        task_id=task_id,
        agent_id="friday",
        purpose="brain_query",
        max_tokens=600,
    )

    return {"message": f"🧠 Brain:\n\n{response.strip()}"}


# ── Busca ──────────────────────────────────────────────────────────────────────

async def _search_knowledge_base(
    query: str,
    brain_owner: str | None = None,
) -> list[dict]:
    """
    Tenta busca vetorial (match_brain_chunks RPC) primeiro.
    Faz fallback para full-text search se RPC falhar ou não retornar resultados.

    Args:
        brain_owner: If set, only return chunks with this brain_owner.
                     None means no filter (unrestricted access).
    """
    # Tenta vector search via pgvector RPC
    try:
        embedding = await _get_embedding(query)
        if embedding:
            rpc_params: dict = {
                "query_embedding": embedding,
                "pipeline_type_in": "mauro",
                "client_id_in": None,
                "match_count": 6,
            }
            # B1-03: pass brain_owner to RPC if the function supports it
            if brain_owner is not None:
                rpc_params["brain_owner_in"] = brain_owner

            rpc_result = await asyncio.to_thread(
                lambda: supabase.rpc(
                    "match_brain_chunks",
                    rpc_params,
                ).execute()
            )  # type: ignore

            results = rpc_result.data or []

            # B1-03: client-side filter as safety net (in case RPC ignores the param)
            if brain_owner is not None and results:
                results = [
                    r for r in results
                    if r.get("brain_owner") == brain_owner
                    or r.get("brain_owner") is None  # legacy rows without brain_owner
                ]

            # B3-01: exclude rejected chunks from brain queries
            results = [
                r for r in results
                if r.get("curation_status", "pending") != "rejected"
            ]

            if results:
                return results
    except Exception as e:
        print(f"[brain_query] vector search failed (using text fallback): {e}")

    # Fallback: full-text search por palavras-chave
    return await _text_search(query, brain_owner=brain_owner)


async def _text_search(
    query: str,
    brain_owner: str | None = None,
) -> list[dict]:
    """Full-text search simples na tabela knowledge_base.

    Args:
        brain_owner: If set, only return rows with this brain_owner.
    """
    # Usa as primeiras 3 palavras significativas para busca
    words = [w for w in query.split() if len(w) > 3][:3]
    if not words:
        words = query.split()[:2]

    search_term = " | ".join(words)  # OR entre termos

    def _apply_owner_filter(q):
        """B1-03: apply brain_owner filter if set."""
        if brain_owner is not None:
            return q.eq("brain_owner", brain_owner)
        return q

    try:
        result = await asyncio.to_thread(
            lambda: _apply_owner_filter(
                supabase.table("knowledge_base")
                .select("id,type,content,source,client_id")
                .text_search("content", search_term)
            )
            .limit(6)
            .execute()
        )
        return result.data or []
    except Exception:
        # Se text_search não estiver disponível, tenta ilike simples
        try:
            first_word = words[0] if words else query[:20]
            result = await asyncio.to_thread(
                lambda: _apply_owner_filter(
                    supabase.table("knowledge_base")
                    .select("id,type,content,source,client_id")
                    .ilike("content", f"%{first_word}%")
                )
                .limit(6)
                .execute()
            )
            return result.data or []
        except Exception as e2:
            print(f"[brain_query] text search failed: {e2}")
            return []


async def _get_embedding(text: str) -> list[float] | None:
    """
    Gera embedding via OpenAI (se disponível) para busca vetorial.
    Retorna None se não configurado — faz fallback para text search.
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": text},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception:
        return None


# ── Formatação ─────────────────────────────────────────────────────────────────

def _format_chunks(chunks: list[dict]) -> str:
    """Formata os chunks para o prompt do Claude."""
    lines = []
    for i, chunk in enumerate(chunks, 1):
        tipo = chunk.get("type") or "info"
        content = (chunk.get("content") or "")[:800]
        source = chunk.get("source") or ""
        source_info = f" (fonte: {source})" if source else ""
        lines.append(f"[{i}] [{tipo}]{source_info}\n{content}")
    return "\n\n---\n\n".join(lines)
