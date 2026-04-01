"""
brain_ingest handler — alimenta o Brain com conhecimento novo.

"Brain, aprende isso: [conteúdo]"
"Brain, salva: [conteúdo]"

Salva na tabela knowledge_base com source="friday_ingest".
Schema: id, client_id, type, content, source, conversation_id, relevance, created_at
"""
from __future__ import annotations

import asyncio

from runtime.config import settings
from runtime.db import supabase


async def handle_brain_ingest(task: dict) -> dict:
    """
    Salva conteúdo na knowledge_base.
    Retorna confirmação com resumo do que foi registrado.
    """
    payload = task.get("payload", {})
    content = payload.get("content") or payload.get("original_text", "")
    tipo = payload.get("type") or "info"
    source = payload.get("source") or "friday_ingest"

    if not content:
        return {"message": "Brain: não recebi conteúdo para registrar. Tente: 'Brain, aprende isso: [texto]'"}

    # Remove prefixos de comando do conteúdo
    import re
    content = re.sub(
        r"^(brain[,.]?\s*)?(aprende\s+(isso|que)|salva[,:]?|registra[,:]?|anota[,:]?)\s*:?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    ).strip()

    if not content:
        return {"message": "Brain: conteúdo vazio após processar o comando. Tente novamente com mais texto."}

    try:
        await asyncio.to_thread(
            lambda: supabase.table("knowledge_base").insert({
                "client_id": settings.sparkle_internal_client_id,
                "type": tipo,
                "content": content,
                "source": source,
                "relevance": "high",
            }).execute()
        )
    except Exception as e:
        print(f"[brain_ingest] failed to insert: {e}")
        return {"message": f"Brain: erro ao registrar conhecimento — {e}"}

    # Resumo do que foi salvo
    preview = content[:120] + ("..." if len(content) > 120 else "")
    return {
        "message": (
            f"Anotado! ✅\n\n"
            f"{preview}\n\n"
            f"KB atualizado."
        )
    }
