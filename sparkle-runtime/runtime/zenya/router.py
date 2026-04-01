"""
Zenya router — endpoints para integração n8n → Runtime.

POST /zenya/learn  — Recebe notificação do n8n ao final de uma conversa Zenya
                     e enfileira task learn_from_conversation para extração de KB.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from runtime.db import supabase

router = APIRouter()


# ── Request models ─────────────────────────────────────────

class ZenyaLearnRequest(BaseModel):
    """
    Payload enviado pelo n8n ao encerrar uma conversa Zenya.

    Campos:
    - phone: número do cliente final (ex: "5511999998888")
    - client_id: UUID do cliente Sparkle (ex: "uuid-da-plaka")
    - client_name: nome legível do cliente (ex: "Plaka", "Confeitaria Alexsandro")
    - conversation_text: texto completo da conversa, formato livre
                         (ex: "Cliente: oi\nZenya: olá, como posso ajudar?")
    """
    phone: str
    client_id: str
    client_name: str = "Cliente Zenya"
    conversation_text: str


# ── Endpoints ──────────────────────────────────────────────

@router.post("/learn")
async def zenya_learn(req: ZenyaLearnRequest, background_tasks: BackgroundTasks):
    """
    Recebe notificação do n8n quando uma conversa Zenya encerra.
    Enfileira task learn_from_conversation em background.
    Responde 200 imediatamente — não bloqueia o n8n.

    Exemplo de payload:
    {
        "phone": "5511999998888",
        "client_id": "uuid-plaka",
        "client_name": "Plaka",
        "conversation_text": "Cliente: oi\\nZenya: olá! como posso ajudar?"
    }
    """
    background_tasks.add_task(
        _enqueue_learn,
        phone=req.phone,
        client_id=req.client_id,
        client_name=req.client_name,
        conversation_text=req.conversation_text,
    )
    return {
        "status": "queued",
        "message": f"Aprendizado de conversa enfileirado para {req.client_name} ({req.phone})",
    }


# ── Background helpers ─────────────────────────────────────

async def _enqueue_learn(
    phone: str,
    client_id: str,
    client_name: str,
    conversation_text: str,
) -> None:
    """
    Converte conversation_text em lista de mensagens e insere
    task learn_from_conversation na fila do Runtime.
    """
    try:
        conversation = _parse_conversation(conversation_text)

        if len(conversation) < 2:
            print(f"[zenya/learn] Conversa de {phone} muito curta — ignorando")
            return

        conversation_id = f"zenya_{client_id}_{phone}_{len(conversation)}msgs"

        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": client_id,
                "task_type": "learn_from_conversation",
                "payload": {
                    "client_id": client_id,
                    "client_name": client_name,
                    "conversation": conversation,
                    "conversation_id": conversation_id,
                },
                "status": "pending",
                "priority": 3,
            }).execute()
        )
        print(
            f"[zenya/learn] Task learn_from_conversation enfileirada: "
            f"{client_name} / {phone} ({len(conversation)} msgs)"
        )
    except Exception as e:
        print(f"[zenya/learn] Falha ao enfileirar aprendizado para {phone}: {e}")


def _parse_conversation(text: str) -> list[dict]:
    """
    Converte texto de conversa em lista de dicts {role, content}.

    Suporta dois formatos:
    1. "Cliente: mensagem\\nZenya: resposta" (formato n8n padrão)
    2. "user: mensagem\\nassistant: resposta" (formato nativo Runtime)

    Linhas sem prefixo reconhecido são ignoradas silenciosamente.
    """
    result = []
    user_prefixes = ("cliente:", "user:", "usuario:", "usuário:")
    assistant_prefixes = ("zenya:", "assistant:", "atendente:", "bot:")

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        lower = line.lower()

        for prefix in user_prefixes:
            if lower.startswith(prefix):
                content = line[len(prefix):].strip()
                if content:
                    result.append({"role": "user", "content": content})
                break
        else:
            for prefix in assistant_prefixes:
                if lower.startswith(prefix):
                    content = line[len(prefix):].strip()
                    if content:
                        result.append({"role": "assistant", "content": content})
                    break

    return result
