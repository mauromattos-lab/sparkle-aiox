"""
mark_contract_signed handler — Story 1.2 (AC-4.1)

Fallback manual: marca contrato como assinado para casos onde o cliente
nao assina digitalmente via Autentique (upload manual ou assinatura fisica).

Task payload:
{
    "client_id": "<uuid>"
}
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log_event(client_id: str, event_type: str, payload: dict) -> None:
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_events").insert({
                "client_id": client_id,
                "event_type": event_type,
                "phase": "contract",
                "payload": payload,
            }).execute()
        )
    except Exception as e:
        logger.warning("[mark_contract_signed] falha ao registrar evento '%s': %s", event_type, e)


async def _alert_friday(message: str) -> None:
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        logger.warning("[mark_contract_signed] MAURO_WHATSAPP nao configurado — alerta nao enviado: %s", message)
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, f"[Friday] {message}")
    except Exception as e:
        logger.warning("[mark_contract_signed] falha ao alertar Friday: %s", e)


async def handle_mark_contract_signed(task: dict) -> dict:
    """
    AC-4.1 — Fallback manual: marca gates_passed.contract = true.

    Usado quando cliente nao assina digitalmente.
    Mauro (ou agente) chama esta task manualmente.

    Payload: { "client_id": "<uuid>" }
    """
    payload = task.get("payload", {})
    client_id = (payload.get("client_id") or task.get("client_id") or "").strip()

    if not client_id:
        return {"status": "error", "error": "client_id e obrigatorio"}

    # Busca workflow da fase contract
    try:
        wf_res = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("id, gate_details, gate_passed")
            .eq("client_id", client_id)
            .eq("phase", "contract")
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("[mark_contract_signed] falha ao buscar workflow client_id=%s: %s", client_id, e)
        return {"status": "error", "error": f"Falha ao buscar onboarding_workflows: {e}"}

    wf = wf_res.data if wf_res else None
    if not wf:
        return {
            "status": "error",
            "error": f"Fase 'contract' nao encontrada para client_id={client_id}",
        }

    # Merge gate_details com contract_signed=true
    current_gate = wf.get("gate_details") or {}
    updated_gate = {
        **current_gate,
        "contract_signed": True,
        "contract_signed_at": _now(),
        "contract_signed_manual": True,
        "updated_at": _now(),
    }

    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "gate_details": updated_gate,
                "updated_at": _now(),
            })
            .eq("id", wf["id"])
            .execute()
        )
        logger.info("[mark_contract_signed] contract_signed=true definido para client_id=%s", client_id)
    except Exception as e:
        logger.error("[mark_contract_signed] falha ao atualizar gate_details client_id=%s: %s", client_id, e)
        return {"status": "error", "error": f"Falha ao atualizar gate_details: {e}"}

    # Busca nome do cliente para alerta
    client_name = client_id
    try:
        c_res = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("name")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        if c_res and c_res.data:
            client_name = c_res.data.get("name", client_id)
    except Exception:
        pass

    # Registra evento
    await _log_event(
        client_id=client_id,
        event_type="contract_signed",
        payload={
            "manual": True,
            "signed_at": _now(),
        },
    )

    # Alerta Friday (AC-3.5)
    await _alert_friday(
        f"Contrato de {client_name} marcado como assinado manualmente. "
        "Aguardando pagamento para Gate 1."
    )

    return {
        "status": "ok",
        "client_id": client_id,
        "client_name": client_name,
        "contract_signed": True,
        "manual": True,
    }
