"""
Handoff Schema Validator — Story 1.3.

Valida o bloco de handoff obrigatório do sparkle-os-process-v2.
Armazena handoffs válidos em runtime_tasks para auditoria.
Garante one-time use via campo consumed.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from pydantic import BaseModel

from runtime.db import supabase


# ── Schema de entrada ──────────────────────────────────────────────

class HandoffPayload(BaseModel):
    gate_concluido: Optional[str] = None
    status: Optional[str] = None
    proximo: Optional[str] = None
    sprint_item: Optional[str] = None
    entrega: Optional[list[str]] = None
    supabase_atualizado: Optional[bool] = None
    prompt_para_proximo: Optional[str] = None


# ── Validação ──────────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "gate_concluido", "status", "proximo",
    "sprint_item", "entrega", "supabase_atualizado", "prompt_para_proximo",
]


def validate_handoff(payload: HandoffPayload) -> tuple[bool, list[str]]:
    """Valida presença de campos obrigatórios + regras de negócio. Retorna (valid, errors)."""
    errors = []

    # Campos obrigatórios ausentes
    for field in REQUIRED_FIELDS:
        val = getattr(payload, field, None)
        if val is None:
            errors.append(f"{field}: campo obrigatório ausente")

    if errors:
        return False, errors

    # Regras de negócio
    if not payload.entrega:
        errors.append("entrega: deve ter pelo menos 1 item")
    if not payload.supabase_atualizado:
        errors.append("supabase_atualizado: deve ser true — execute POST /system/state antes")
    if len(payload.prompt_para_proximo) < 100:
        errors.append(
            f"prompt_para_proximo: muito curto ({len(payload.prompt_para_proximo)} chars, mínimo 100)"
        )
    if not payload.proximo.startswith("@"):
        errors.append("proximo: deve referenciar um agente com @ (ex: '@po')")

    return len(errors) == 0, errors


async def store_handoff(payload: HandoffPayload) -> str:
    """Armazena handoff válido em runtime_tasks. Retorna handoff_validation_id."""
    validation_id = str(uuid.uuid4())

    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "system",
            "task_type": "handoff_validation",
            "payload": {
                "handoff_validation_id": validation_id,
                "gate_concluido": payload.gate_concluido,
                "sprint_item": payload.sprint_item,
                "proximo": payload.proximo,
                "status": payload.status,
                "entrega": payload.entrega,
                "prompt_para_proximo": payload.prompt_para_proximo[:200],
                "consumed": False,
            },
            "status": "done",
            "priority": 5,
        }).execute()
    )
    return validation_id


async def consume_handoff(handoff_validation_id: str) -> dict:
    """
    Marca handoff como consumido (one-time use).
    Retorna {'allowed': bool, 'reason': str}.
    """
    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("id,payload,status")
        .eq("task_type", "handoff_validation")
        .execute()
    )

    records = result.data or []
    match = next(
        (r for r in records
         if r.get("payload", {}).get("handoff_validation_id") == handoff_validation_id),
        None,
    )

    if not match:
        return {"allowed": False, "reason": "handoff_validation_id nao encontrado"}

    if match.get("payload", {}).get("consumed", False):
        return {"allowed": False, "reason": "handoff_validation_id ja foi utilizado"}

    # Marcar como consumido
    payload = dict(match["payload"])
    payload["consumed"] = True
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .update({"payload": payload})
        .eq("id", match["id"])
        .execute()
    )

    return {"allowed": True, "reason": "Handoff valido e consumido"}
