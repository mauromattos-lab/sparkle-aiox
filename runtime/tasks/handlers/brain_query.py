"""
brain_query handler — S8-P1 refactor + S8-P3 threshold de similaridade.

Fluxo:
  1. Extrai query + owner_type do payload
  2. Mapeia owner_type → pipeline_type para brain_chunks
  3. Tenta busca vetorial via match_brain_chunks RPC (se BRAIN_EMBEDDINGS_ENABLED=true)
  4. Aplica BRAIN_SIMILARITY_THRESHOLD para filtrar resultados abaixo do limiar
  5. Fallback: busca textual via search_brain_text RPC (sempre disponível)
  6. Claude Haiku sintetiza, retorna para Friday/Zenya

owner_type routing:
  'mauro'  → pipeline_type='mauro', client_id=NULL
  'client' → pipeline_type='cliente', client_id=<uuid>

S8-P3: threshold configurável via BRAIN_SIMILARITY_THRESHOLD env var (default 0.75).
  Resultados com similarity < threshold são descartados. Se threshold eliminar
  todos os resultados do vector search, fallback para text search é acionado.
"""
from __future__ import annotations

import asyncio

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.embeddings import generate_embedding
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
    owner_type = payload.get("owner_type", "mauro")  # default: mauro (Friday)
    client_id = payload.get("client_id")

    if not query:
        return {"message": "Brain: nenhuma query recebida. Como posso ajudar?"}

    task_id = task.get("id")
    chunks = await _search_knowledge_base(query, owner_type=owner_type, client_id=client_id)

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

async def _search_knowledge_base(query: str, owner_type: str = "mauro", client_id: str | None = None) -> list[dict]:
    """
    Busca no brain_chunks com isolamento por owner_type.

    Fluxo S8-P3:
    1. Tenta vector search via match_brain_chunks RPC (se embedding disponível para a query)
    2. Aplica BRAIN_SIMILARITY_THRESHOLD — descarta resultados abaixo do limiar
    3. Se threshold eliminou tudo ou não há embedding, faz fallback para text search

    owner_type='mauro'  → pipeline_type='mauro'
    owner_type='client' → pipeline_type='cliente' + client_id obrigatório
    """
    pipeline_type = "mauro" if owner_type == "mauro" else "cliente"
    client_uuid = None
    if owner_type == "client" and client_id:
        try:
            from uuid import UUID
            client_uuid = str(UUID(client_id))
        except ValueError:
            print(f"[brain_query] client_id inválido: {client_id}")

    # Tenta vector search via pgvector RPC
    try:
        embedding = await generate_embedding(query)
        if embedding:
            rpc_params = {
                "query_embedding": embedding,
                "pipeline_type_in": pipeline_type,
                "match_count": 6,
            }
            if client_uuid:
                rpc_params["client_id_in"] = client_uuid

            rpc_result = await asyncio.to_thread(
                lambda: supabase.rpc("match_brain_chunks", rpc_params).execute()
            )

            if rpc_result.data:
                # S8-P3: filtrar por threshold de similaridade
                threshold = settings.brain_similarity_threshold
                filtered = [
                    r for r in rpc_result.data
                    if r.get("similarity", 0) >= threshold
                ]

                if filtered:
                    print(
                        f"[brain_query] S8-P3: vector search retornou {len(rpc_result.data)} chunks, "
                        f"{len(filtered)} acima do threshold={threshold}"
                    )
                    return [
                        {
                            "type": r.get("source_type", "info"),
                            "content": r.get("canonical_text") or r.get("narrative_text", ""),
                            "source": r.get("pipeline_type", ""),
                            "client_id": str(r.get("client_id") or ""),
                            "similarity": r.get("similarity"),
                        }
                        for r in filtered
                    ]
                else:
                    print(
                        f"[brain_query] S8-P3: {len(rpc_result.data)} chunks retornados mas todos "
                        f"abaixo do threshold={threshold} — fallback para text search"
                    )
            # Se não há dados ou threshold eliminou tudo → cai para text search
    except Exception as e:
        print(f"[brain_query] S8-P1/P3: vector search falhou (fallback text): {e}")

    # Fallback: busca textual via RPC search_brain_text
    try:
        text_params = {
            "query_text": query,
            "pipeline_type_in": pipeline_type,
            "match_count": 6,
        }
        if client_uuid:
            text_params["client_id_in"] = client_uuid

        text_result = await asyncio.to_thread(
            lambda: supabase.rpc("search_brain_text", text_params).execute()
        )
        if text_result.data:
            print(f"[brain_query] text search retornou {len(text_result.data)} chunks")
            return [
                {
                    "type": r.get("source_type", "info"),
                    "content": r.get("content", ""),
                    "source": r.get("pipeline_type", ""),
                    "client_id": "",
                }
                for r in text_result.data
            ]
    except Exception as e:
        print(f"[brain_query] S8-P1: text search falhou: {e}")

    return []


# ── Formatação ─────────────────────────────────────────────────────────────────

def _format_chunks(chunks: list[dict]) -> str:
    """Formata os chunks para o prompt do Claude."""
    lines = []
    for i, chunk in enumerate(chunks, 1):
        tipo = chunk.get("type") or "info"
        content = (chunk.get("content") or "")[:800]
        source = chunk.get("source") or ""
        similarity = chunk.get("similarity")
        source_info = f" (fonte: {source})" if source else ""
        sim_info = f" [sim={similarity:.3f}]" if similarity is not None else ""
        lines.append(f"[{i}] [{tipo}]{source_info}{sim_info}\n{content}")
    return "\n\n---\n\n".join(lines)
