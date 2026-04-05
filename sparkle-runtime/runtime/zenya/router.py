"""
Zenya router — Webhook multi-tenant por cliente + integração n8n → Runtime.

POST /zenya/webhook/{client_id}  — Webhook Z-API por cliente (substitui n8n para novos clientes)
POST /zenya/learn                — Recebe notificação do n8n ao final de uma conversa Zenya
                                   e enfileira task learn_from_conversation para extração de KB.
GET  /zenya/clients              — Lista clientes Zenya ativos no Runtime.

Multi-tenant: cada client_id tem suas próprias credenciais Z-API no Supabase (tabela zenya_clients).
"""
from __future__ import annotations

import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from runtime.db import supabase
from runtime.friday.transcriber import transcribe_url

router = APIRouter()


# ── Soul Prompt Resolution (SYS-4) ────────────────────────

_FALLBACK_SOUL_PROMPT = "Voce e a Zenya, assistente de atendimento. Responda de forma acolhedora e profissional."


def _resolve_soul_prompt(client_config: dict) -> str:
    """Prioridade: soul_prompt manual > soul_prompt_generated > fallback generico."""
    manual = (client_config.get("soul_prompt") or "").strip()
    generated = (client_config.get("soul_prompt_generated") or "").strip()
    if manual:
        return manual
    if generated:
        return generated
    return _FALLBACK_SOUL_PROMPT


# ── Zenya Webhook (multi-tenant) ───────────────────────────

class ZAPIWebhookPayload(BaseModel):
    phone: Optional[str] = None
    fromMe: Optional[bool] = False
    text: Optional[dict] = None
    audio: Optional[dict] = None
    type: Optional[str] = None


async def _get_client_config(client_id: str) -> dict | None:
    """Carrega configuração do cliente (credenciais Z-API, soul_prompt) do Supabase.

    Lookup order:
    1. Try client_id as UUID (canonical)
    2. Fallback: try display_slug for backward compatibility with old URLs
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("*")
            .eq("client_id", client_id)
            .eq("active", True)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        pass

    # Fallback: lookup by display_slug (old slug-based URLs)
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("*")
            .eq("display_slug", client_id)
            .eq("active", True)
            .single()
            .execute()
        )
        if result.data:
            print(f"[zenya] cliente {client_id} encontrado via display_slug fallback")
            return result.data
    except Exception:
        pass

    print(f"[zenya] cliente {client_id} não encontrado por UUID nem display_slug")
    return None


async def _send_zenya_message(client_config: dict, phone: str, message: str) -> None:
    """Envia mensagem via Z-API com credenciais do cliente."""
    zapi_instance = client_config.get("zapi_instance_id")
    zapi_token = client_config.get("zapi_token")
    zapi_client_token = client_config.get("zapi_client_token", "")

    if not zapi_instance or not zapi_token:
        print(f"[zenya] credenciais Z-API ausentes para cliente {client_config.get('client_id')}")
        return

    url = f"https://api.z-api.io/instances/{zapi_instance}/token/{zapi_token}/send-text"
    headers = {"Client-Token": zapi_client_token} if zapi_client_token else {}

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json={"phone": phone, "message": message},
                headers=headers,
                timeout=10.0,
            )
    except Exception as e:
        print(f"[zenya] falha ao enviar mensagem: {e}")


async def _process_zenya_message(
    client_id: str, text: str, phone: str, client_config: dict
) -> None:
    """Processa mensagem via Character Runtime com contexto do cliente."""
    try:
        task_result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "zenya",
                "client_id": client_id,
                "task_type": "send_character_message",
                "payload": {
                    "character": "zenya",
                    "message": text,
                    "phone": phone,
                    "soul_prompt": _resolve_soul_prompt(client_config),
                    "lore": client_config.get("lore", ""),
                    "client_name": client_config.get("business_name", ""),
                },
                "status": "pending",
                "priority": 8,
            }).execute()
        )
        task = task_result.data[0] if task_result.data else {}
        if not task:
            return

        from runtime.tasks.worker import execute_task
        await execute_task(task)

        # Busca resultado e envia via Z-API do cliente
        result_data = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("result,status")
            .eq("id", task["id"])
            .single()
            .execute()
        )
        task_result_data = result_data.data or {}
        if task_result_data.get("status") == "done":
            result = task_result_data.get("result") or {}
            response_text = result.get("message") or result.get("response", "")
            if response_text and phone:
                await _send_zenya_message(client_config, phone, response_text)
    except Exception as e:
        print(f"[zenya] falha ao processar mensagem de {phone}: {e}")


@router.post("/webhook/{client_id}")
async def zenya_webhook(
    client_id: str,
    payload: ZAPIWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Webhook Z-API por cliente. Processa em background, responde 200 imediatamente.
    Cada cliente aponta seu número Z-API para: POST /zenya/webhook/{client_id}
    """
    if payload.fromMe:
        return {"status": "ignored", "reason": "fromMe"}

    client_config = await _get_client_config(client_id)
    if not client_config:
        return {"status": "error", "reason": "client_not_found"}

    phone = payload.phone or ""

    if payload.audio and payload.audio.get("audioUrl"):
        async def process_audio():
            transcript = await asyncio.to_thread(transcribe_url, payload.audio["audioUrl"])
            await _process_zenya_message(client_id, transcript, phone, client_config)

        background_tasks.add_task(process_audio)
        return {"status": "queued", "type": "audio", "client_id": client_id}

    if payload.text and payload.text.get("message"):
        background_tasks.add_task(
            _process_zenya_message,
            client_id,
            payload.text["message"],
            phone,
            client_config,
        )
        return {"status": "queued", "type": "text", "client_id": client_id}

    return {"status": "ignored", "reason": "no_content"}


@router.get("/clients")
async def list_zenya_clients():
    """Lista clientes Zenya ativos no Runtime."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("client_id,business_name,active,created_at")
            .eq("active", True)
            .execute()
        )
        return {"clients": result.data or [], "count": len(result.data or [])}
    except Exception as e:
        return {"error": str(e)}


# ── SYS-4: DNA Endpoints ──────────────────────────────────


class DnaUpdateRequest(BaseModel):
    """Campos parciais do DNA para atualizar."""
    identidade: Optional[dict] = None
    tom_voz: Optional[dict] = None
    regras_negocio: Optional[list] = None
    diferenciais: Optional[list] = None
    publico_alvo: Optional[dict] = None
    anti_patterns: Optional[list] = None


@router.get("/clients/{client_id}/dna")
async def get_client_dna(client_id: str):
    """Retorna client_dna atual do cliente."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("client_id,business_name,client_dna,soul_prompt_generated,dna_updated_at")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        return result.data or {"error": "cliente nao encontrado"}
    except Exception as e:
        return {"error": str(e)}


@router.put("/clients/{client_id}/dna")
async def update_client_dna(client_id: str, body: DnaUpdateRequest):
    """Atualiza campos especificos do client_dna JSONB."""
    try:
        current = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("client_dna")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        dna = current.data.get("client_dna") or {} if current.data else {}

        updates = body.model_dump(exclude_none=True)
        dna.update(updates)

        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({"client_dna": dna})
            .eq("client_id", client_id)
            .execute()
        )
        return {"message": f"DNA atualizado: {list(updates.keys())}", "client_id": client_id}
    except Exception as e:
        return {"error": str(e)}


@router.post("/clients/{client_id}/dna/extract")
async def extract_client_dna(client_id: str):
    """Dispara re-extracao de DNA do cliente via task."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "system",
                "client_id": client_id,
                "task_type": "extract_client_dna",
                "payload": {"client_id": client_id, "regenerate_prompt": True},
                "status": "pending",
                "priority": 6,
            }).execute()
        )
        task = result.data[0] if result.data else {}
        # Execute inline (same pattern as scheduler._run_and_execute)
        if task:
            try:
                from runtime.tasks.worker import execute_task
                await execute_task(task)
            except Exception as exec_err:
                logger.warning("[zenya/dna/extract] inline execution failed: %s", exec_err)
        return {"message": "Extracao de DNA concluida", "task_id": task.get("id")}
    except Exception as e:
        return {"error": str(e)}


@router.get("/clients/{client_id}/dna/preview-prompt")
async def preview_soul_prompt(client_id: str):
    """Preview do soul_prompt que seria gerado a partir do DNA atual."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("client_dna,soul_prompt,soul_prompt_generated")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        data = result.data or {}
        dna = data.get("client_dna") or {}
        return {
            "client_id": client_id,
            "dna_layers_filled": sum(1 for k in ("identidade", "tom_voz", "regras_negocio", "diferenciais", "publico_alvo", "anti_patterns") if dna.get(k)),
            "current_soul_prompt_manual": (data.get("soul_prompt") or "")[:200],
            "current_soul_prompt_generated": (data.get("soul_prompt_generated") or "")[:200],
            "active_prompt_source": "manual" if data.get("soul_prompt") else ("generated" if data.get("soul_prompt_generated") else "fallback"),
        }
    except Exception as e:
        return {"error": str(e)}


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
