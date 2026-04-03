"""
Friday router — HTTP endpoints.

POST /friday/message  — plain text message from Mauro
POST /friday/audio    — audio file (multipart) or JSON with audio_url
POST /friday/webhook  — Z-API webhook payload (auto-detects text vs audio)
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel

from runtime.config import settings
from runtime.db import supabase
from runtime.friday.dispatcher import classify_and_dispatch
from runtime.friday.responder import build_response, build_response_plain, build_error_response
from runtime.friday.transcriber import transcribe_bytes, transcribe_url
from runtime.tasks.hydrator import hydrate_context
from runtime.utils.tts import get_tts_info

router = APIRouter()


# ── Request / Response models ──────────────────────────────

class TextMessageRequest(BaseModel):
    text: str
    from_number: str = ""


class AudioUrlRequest(BaseModel):
    audio_url: str
    from_number: str = ""


class ZAPIWebhookPayload(BaseModel):
    """Minimal Z-API webhook shape — extend as needed."""
    phone: Optional[str] = None
    fromMe: Optional[bool] = False
    text: Optional[dict] = None
    audio: Optional[dict] = None
    type: Optional[str] = None


class OnboardRequest(BaseModel):
    """Direct onboarding request (API or internal trigger)."""
    business_name: str
    business_type: str = "negócio"
    site_url: str = ""
    phone: str = ""
    extra_info: str = ""
    client_id: Optional[str] = None


# ── SYS-3.5: Workflow command detection ───────────────────

_WORKFLOW_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # (pattern, template_slug, context_key_for_extracted_value)
    (
        re.compile(r"\b(?:onborda|onboarding)\s+(.+)", re.IGNORECASE),
        "onboarding_zenya",
        "business_name",
    ),
    (
        re.compile(r"\b(?:cria\s+landing|landing\s+page)\s+(.+)", re.IGNORECASE),
        "landing_page_nicho",
        "nicho",
    ),
    (
        re.compile(r"\b(?:conte[uú]do|produz\s+conte[uú]do)\s+(.+)", re.IGNORECASE),
        "content_production",
        "persona",
    ),
]


async def _detect_workflow(text: str) -> Optional[dict]:
    """
    Verifica se o texto corresponde a um comando de workflow.
    Retorna dict com info do workflow ou None se não bater.
    """
    text_clean = text.strip()
    for pattern, template_slug, context_key in _WORKFLOW_PATTERNS:
        match = pattern.search(text_clean)
        if match:
            extracted = match.group(1).strip()
            return {
                "template_slug": template_slug,
                "context_key": context_key,
                "extracted_value": extracted,
            }
    return None


async def _trigger_workflow(template_slug: str, name: str, context: dict) -> dict:
    """
    Faz POST interno para /workflow/start via chamada direta (mesmo processo).
    Retorna o resultado ou erro graceful.
    """
    import httpx

    try:
        # Chamada interna ao próprio servidor (localhost)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://127.0.0.1:8000/workflow/start",
                json={
                    "template_slug": template_slug,
                    "name": name,
                    "context": context,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"[friday] workflow trigger falhou: {resp.status_code} — {resp.text[:200]}")
                return {"error": resp.text[:200]}
    except Exception as e:
        print(f"[friday] workflow trigger erro: {e}")
        return {"error": str(e)}


# ── Endpoints ──────────────────────────────────────────────

@router.get("/tts-info")
async def tts_info():
    """
    Smoke test RT-07 — expõe qual engine TTS está ativa para a Friday.

    Faz um check real na API do ElevenLabs (não apenas variável de ambiente).
    Garante que fallback nunca seja silencioso: status é sempre explícito.

    Retorna:
        engine: "elevenlabs" | "gtts" | null
        voice_id: ID da voz ativa (ElevenLabs) ou null
        voice_name: Nome da voz ou null
        status: "active" | "fallback_active" | "unavailable"
        fallback_available: bool
        fallback_engine: "gtts" | null
    """
    try:
        info = await asyncio.to_thread(get_tts_info)
        return info
    except Exception as e:
        return {
            "engine": None,
            "voice_id": None,
            "voice_name": None,
            "status": "error",
            "fallback_available": False,
            "fallback_engine": None,
            "error": str(e)[:200],
        }


@router.post("/message")
async def receive_message(req: TextMessageRequest, background_tasks: BackgroundTasks):
    """Accept plain text from Mauro and process intent."""
    try:
        # SYS-3.5: Detectar comandos de workflow antes de classificar
        wf = await _detect_workflow(req.text)
        if wf:
            wf_name = f"{wf['template_slug']}_{wf['extracted_value'][:30]}"
            wf_context = {wf["context_key"]: wf["extracted_value"]}
            result = await _trigger_workflow(wf["template_slug"], wf_name, wf_context)
            if "error" not in result:
                return {
                    "status": "ok",
                    "workflow": True,
                    "response": (
                        f"Workflow {wf['template_slug']} iniciado. "
                        f"Vou acompanhar e te atualizar."
                    ),
                    "workflow_result": result,
                }
            # Se workflow falhou (template não existe, etc.), cai no fluxo normal
            print(f"[friday] workflow fallback para chat: {result.get('error', '')[:100]}")

        from runtime.tasks.worker import execute_task
        task = await classify_and_dispatch(req.text, from_number=req.from_number)
        task = hydrate_context(task)
        await execute_task(task)
        response_text = await _wait_for_task(task.get("id"))
        return {"status": "ok", "task_id": task.get("id"), "response": response_text}
    except Exception as e:
        return {"status": "error", "response": build_error_response(e)}


@router.post("/audio")
async def receive_audio_file(file: UploadFile = File(...), from_number: str = ""):
    """Accept audio file upload (OGG/MP3/WAV) and process."""
    try:
        from runtime.tasks.worker import execute_task
        audio_bytes = await file.read()
        transcript = await asyncio.to_thread(transcribe_bytes, audio_bytes, file.filename or "audio.ogg")
        task = await classify_and_dispatch(transcript, from_number=from_number, from_audio=True)
        task = hydrate_context(task)
        await execute_task(task)
        response_text = await _wait_for_task(task.get("id"))
        return {
            "status": "ok",
            "transcript": transcript,
            "task_id": task.get("id"),
            "response": response_text,
        }
    except Exception as e:
        return {"status": "error", "response": build_error_response(e)}


@router.post("/audio-url")
async def receive_audio_url(req: AudioUrlRequest):
    """Accept audio URL (e.g. from Z-API) and process."""
    try:
        from runtime.tasks.worker import execute_task
        transcript = await asyncio.to_thread(transcribe_url, req.audio_url)
        task = await classify_and_dispatch(transcript, from_number=req.from_number, from_audio=True)
        task = hydrate_context(task)
        await execute_task(task)
        response_text = await _wait_for_task(task.get("id"))
        return {
            "status": "ok",
            "transcript": transcript,
            "task_id": task.get("id"),
            "response": response_text,
        }
    except Exception as e:
        return {"status": "error", "response": build_error_response(e)}


@router.post("/onboard")
async def onboard_client(req: OnboardRequest):
    """
    Trigger autonomous client onboarding (Sprint 8).
    Scrapes site, generates KB + system prompt, clones Zenya workflows.
    Long-running (~30-60s): polls until done, returns full result.
    """
    try:
        from runtime.tasks.worker import execute_task
        task = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "onboard_client",
                "payload": {
                    "business_name": req.business_name,
                    "business_type": req.business_type,
                    "site_url": req.site_url,
                    "phone": req.phone,
                    "extra_info": req.extra_info,
                    "client_id": req.client_id,
                },
                "status": "pending",
                "priority": 9,
            }).execute()
        )
        task_record = task.data[0] if task.data else {}
        await execute_task(task_record)
        response_text = await _wait_for_task(task_record.get("id"), timeout=120)
        return {
            "status": "ok",
            "task_id": task_record.get("id"),
            "response": response_text,
        }
    except Exception as e:
        return {"status": "error", "response": build_error_response(e)}


@router.post("/webhook")
async def zapi_webhook(payload: ZAPIWebhookPayload, background_tasks: BackgroundTasks):
    """
    Receive Z-API webhook. Route to audio or text processing.
    Responds 200 immediately (Z-API requires fast ack).
    Processing happens in background.
    """
    if payload.fromMe:
        return {"status": "ignored", "reason": "fromMe"}

    from_number = payload.phone or ""

    if payload.audio and payload.audio.get("audioUrl"):
        background_tasks.add_task(_process_audio_url, payload.audio["audioUrl"], from_number)
        return {"status": "queued", "type": "audio"}

    if payload.text and payload.text.get("message"):
        background_tasks.add_task(_process_text, payload.text["message"], from_number)
        return {"status": "queued", "type": "text"}

    return {"status": "ignored", "reason": "no_content"}


# ── Background helpers ─────────────────────────────────────

async def _maybe_trigger_learning(from_number: str) -> None:
    """
    Verifica se a conversa do número atingiu 10+ mensagens.
    Se sim, enfileira task conversation_summary em background.
    Não bloqueia — silencia todas as exceções.
    """
    if not from_number:
        return
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("conversation_history")
            .select("id", count="exact")
            .eq("phone", from_number)
            .execute()
        )
        count = res.count if res.count is not None else len(res.data or [])
        if count >= 10 and count % 10 == 0:
            # Dispara a cada múltiplo de 10 para evitar flood
            await asyncio.to_thread(
                lambda: supabase.table("runtime_tasks").insert({
                    "agent_id": "friday",
                    "client_id": settings.sparkle_internal_client_id,
                    "task_type": "conversation_summary",
                    "payload": {
                        "phone": from_number,
                        "client_id": settings.sparkle_internal_client_id,
                        "client_name": "Mauro (Friday)",
                    },
                    "status": "pending",
                    "priority": 2,
                }).execute()
            )
            print(f"[friday] Observer: conversation_summary enfileirada para {from_number} ({count} msgs)")
    except Exception as e:
        print(f"[friday] Observer: falha ao verificar histórico de {from_number}: {e}")


async def _process_text(text: str, from_number: str) -> None:
    from runtime.integrations.zapi import send_text
    from runtime.tasks.worker import execute_task
    try:
        # SYS-3.5: Detectar comandos de workflow antes de classificar
        wf = await _detect_workflow(text)
        if wf:
            wf_name = f"{wf['template_slug']}_{wf['extracted_value'][:30]}"
            wf_context = {wf["context_key"]: wf["extracted_value"]}
            result = await _trigger_workflow(wf["template_slug"], wf_name, wf_context)
            if "error" not in result:
                response = (
                    f"Workflow {wf['template_slug']} iniciado. "
                    f"Vou acompanhar e te atualizar."
                )
                if from_number:
                    await asyncio.to_thread(send_text, from_number, response)
                return
            # Se workflow falhou, cai no fluxo normal
            print(f"[friday] workflow fallback para chat: {result.get('error', '')[:100]}")

        task = await classify_and_dispatch(text, from_number=from_number)
        task = hydrate_context(task)
        await execute_task(task)
        response = await _wait_for_task(task.get("id"), timeout=30)
        if from_number:
            await asyncio.to_thread(send_text, from_number, response)
        # Observer: dispara aprendizado em background sem bloquear resposta
        asyncio.create_task(_maybe_trigger_learning(from_number))
    except Exception as e:
        if from_number:
            from runtime.integrations.zapi import send_text as _send
            await asyncio.to_thread(_send, from_number, build_error_response(e))


async def _process_audio_url(audio_url: str, from_number: str) -> None:
    from runtime.integrations.zapi import send_text, send_audio
    from runtime.tasks.worker import execute_task
    from runtime.utils.tts import text_to_audio_url
    try:
        print(f"[friday] Áudio recebido de {from_number!r}, transcrevendo...")
        transcript = await asyncio.to_thread(transcribe_url, audio_url)
        task = await classify_and_dispatch(transcript, from_number=from_number, from_audio=True)
        task = hydrate_context(task)
        await execute_task(task)
        response = await _wait_for_task(task.get("id"), timeout=30)
        if from_number:
            import re
            plain_response = re.sub(r'\*+([^*]+)\*+', r'\1', response)
            plain_response = re.sub(r'_([^_]+)_', r'\1', plain_response)
            plain_response = re.sub(r'^#+\s*', '', plain_response, flags=re.MULTILINE)
            tts_url = text_to_audio_url(plain_response)
            if tts_url:
                print(f"[friday] Respondendo em áudio: {tts_url}")
                await asyncio.to_thread(send_audio, from_number, tts_url)
            else:
                print("[friday] TTS falhou — usando fallback texto")
                await asyncio.to_thread(send_text, from_number, response)
        # Observer: dispara aprendizado em background sem bloquear resposta
        asyncio.create_task(_maybe_trigger_learning(from_number))
    except Exception as e:
        if from_number:
            from runtime.integrations.zapi import send_text as _send
            await asyncio.to_thread(_send, from_number, build_error_response(e))


async def _wait_for_task(task_id: Optional[str], timeout: int = 20) -> str:
    """
    Poll Supabase until the task is done or failed.
    Returns the response string.
    Uses asyncio.sleep to avoid blocking the FastAPI event loop.
    """
    if not task_id:
        return "Tarefa criada mas sem ID — verifica os logs."

    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").select("*").eq("id", task_id).single().execute()
        )
        task = result.data or {}
        if task.get("status") in ("done", "failed"):
            return build_response(task)
        await asyncio.sleep(1)

    return "A tarefa está demorando mais que o esperado. Mauro, verifica os logs."
