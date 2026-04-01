"""
brain_ingest handler — S8-P1 refactor + S8-P3 embeddings.

Rotas:
  owner_type='mauro'           → brain_chunks (pipeline_type='mauro', client_id=NULL)
  owner_type='client'          → brain_chunks (pipeline_type='cliente', client_id=<uuid>)

Payload obrigatório:
  content: str           — conteúdo a ingerir
  owner_type: str        — 'mauro' | 'client' (obrigatório, sem default)
  client_id: str | None  — UUID do cliente (obrigatório se owner_type='client')
  source: str            — origem do conteúdo (opcional, default: 'friday_ingest')
  type: str              — tipo semântico (opcional, default: 'info')

S8-P3: após INSERT bem-sucedido, dispara background task para gerar embedding via
  runtime/utils/embeddings.py. Controlado por BRAIN_EMBEDDINGS_ENABLED env var.
  Falha na geração de embedding não bloqueia a resposta de ingestão.
"""
from __future__ import annotations

import asyncio
import re
from uuid import UUID

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.embeddings import generate_embedding


async def handle_brain_ingest(task: dict) -> dict:
    payload = task.get("payload", {})
    content = payload.get("content") or payload.get("original_text", "")
    owner_type = payload.get("owner_type")  # OBRIGATÓRIO — sem default
    client_id_raw = payload.get("client_id")
    source = payload.get("source") or "friday_ingest"
    tipo = payload.get("type") or "info"

    # Validação: owner_type obrigatório
    if not owner_type:
        return {
            "message": "Brain: campo 'owner_type' é obrigatório. Use 'mauro' ou 'client'.",
            "error": "missing_owner_type",
            "http_status": 400,
        }

    if owner_type not in ("mauro", "client"):
        return {
            "message": f"Brain: owner_type inválido '{owner_type}'. Use 'mauro' ou 'client'.",
            "error": "invalid_owner_type",
            "http_status": 400,
        }

    # Validação: client_id obrigatório quando owner_type='client'
    client_id: UUID | None = None
    if owner_type == "client":
        if not client_id_raw:
            return {
                "message": "Brain: 'client_id' é obrigatório quando owner_type='client'.",
                "error": "missing_client_id",
                "http_status": 400,
            }
        try:
            client_id = UUID(str(client_id_raw))
        except ValueError:
            return {
                "message": f"Brain: client_id inválido '{client_id_raw}'. Deve ser UUID.",
                "error": "invalid_client_id",
                "http_status": 400,
            }

    # Limpar prefixos de comando do conteúdo
    content = re.sub(
        r"^(brain[,.]?\s*)?(aprende\s+(isso|que)|salva[,:]?|registra[,:]?|anota[,:]?)\s*:?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    ).strip()

    if not content:
        return {"message": "Brain: conteúdo vazio após processar o comando. Tente novamente."}

    # Mapear owner_type para pipeline_type da tabela brain_chunks
    pipeline_type = "mauro" if owner_type == "mauro" else "cliente"

    try:
        row = {
            "pipeline_type": pipeline_type,
            "source_type": tipo,
            "source_title": source,
            "raw_content": content,
            "canonical_content": content,
            "chunk_metadata": {
                "owner_type": owner_type,
                "source": source,
                "ingested_by": "friday_ingest",
            },
            "processed_stages": ["ingested"],
        }
        if client_id is not None:
            row["client_id"] = str(client_id)
        # specialist_id e embedding ficam NULL — P3 popula o embedding via background task

        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks").insert(row).execute()
        )
    except Exception as e:
        print(f"[brain_ingest] S8-P1: falha ao inserir em brain_chunks: {e}")
        return {"message": f"Brain: erro ao registrar conhecimento — {e}"}

    # S8-P3: disparar background task para gerar embedding (não bloqueia resposta)
    try:
        inserted_rows = result.data or []
        if inserted_rows:
            chunk_id = inserted_rows[0]["id"]
            asyncio.create_task(
                _generate_and_update_embedding(chunk_id, content)
            )
    except Exception as e:
        # Falha no agendamento da task não bloqueia a ingestão
        print(f"[brain_ingest] WARNING: não foi possível agendar geração de embedding: {e}")

    preview = content[:120] + ("..." if len(content) > 120 else "")
    namespace = "Mauro" if owner_type == "mauro" else f"Cliente {client_id_raw}"
    return {
        "message": f"Anotado no Brain [{namespace}]! ✅\n\n{preview}\n\nKB atualizado.",
        "owner_type": owner_type,
        "pipeline_type": pipeline_type,
    }


async def _generate_and_update_embedding(chunk_id: str, content: str) -> None:
    """
    Background task: gera embedding via OpenAI e atualiza o chunk inserido.

    Executada via asyncio.create_task() — não bloqueia a resposta de ingestão.
    Controlada por BRAIN_EMBEDDINGS_ENABLED env var.
    Falha silenciosa — log de WARNING emitido, chunk permanece sem embedding
    e fallback text search continua funcionando.
    """
    embedding = await generate_embedding(content)
    if embedding:
        try:
            await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .update({"embedding": embedding})
                .eq("id", chunk_id)
                .execute()
            )
            print(f"[brain_ingest] S8-P3: embedding atualizado para chunk {chunk_id}")
        except Exception as e:
            print(f"[brain_ingest] WARNING: falha ao salvar embedding para {chunk_id}: {e}")
    else:
        print(
            f"[brain_ingest] WARNING: embedding não gerado para {chunk_id} "
            "— busca vetorial não disponível para este chunk (fallback text search ativo)"
        )
