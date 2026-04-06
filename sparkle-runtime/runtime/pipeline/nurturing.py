"""
LIFECYCLE-2.2 — Lead Nurturing Engine.

Routes WARM (BANT 40-79) and COLD (BANT < 40) leads into automated
nurturing sequences. HOT leads (>=80) are NOT affected.

WARM sequence: Day 0 case study, Day 2 comparison, Day 5 re-qualify
COLD sequence: Day 0 educational, Day 7 educational, Day 14 re-qualify, Day 30 archive
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

def _now():
    return datetime.now(timezone.utc)

WARM_SEQUENCE = [
    {"step": 0, "day": 0, "type": "case_study",
     "message": "Oi {name}! Separei um caso real de como uma empresa do seu segmento transformou o atendimento com IA. Quer dar uma olhada?"},
    {"step": 1, "day": 2, "type": "comparison",
     "message": "Oi {name}! Empresas do seu segmento que usam IA no WhatsApp atendem 5x mais clientes sem aumentar equipe. Quer ver um comparativo antes/depois?"},
    {"step": 2, "day": 5, "type": "requalify",
     "message": "Oi {name}! Quantos atendimentos por dia voces fazem no WhatsApp hoje? E qual o maior desafio? Quero ver se faz sentido pra voces."},
]

COLD_SEQUENCE = [
    {"step": 0, "day": 0, "type": "educational",
     "message": "Oi {name}! Sabia que 73% das PMEs brasileiras ja usam WhatsApp para vender? A IA esta mudando o jogo."},
    {"step": 1, "day": 7, "type": "educational_2",
     "message": "Oi {name}! Muitas empresas perdem vendas fora do horario comercial. Um atendente IA resolve isso — funciona 24h, sem folga."},
    {"step": 2, "day": 14, "type": "requalify_light",
     "message": "Oi {name}! Rapida: voces atendem clientes pelo WhatsApp? Se sim, posso mostrar como automatizar sem perder a qualidade."},
    {"step": 3, "day": 30, "type": "archive", "message": None},
]


async def route_lead_by_temperature(lead_id: str, bant_score: int) -> dict:
    if bant_score >= 80:
        return {"lead_id": lead_id, "action": "hot_path"}

    sequence_type = "warm" if bant_score >= 40 else "cold"
    nurturing_state = {
        "sequence_type": sequence_type,
        "current_step": 0,
        "started_at": _now().isoformat(),
        "next_send_at": _now().isoformat(),
    }

    await asyncio.to_thread(
        lambda: supabase.table("leads")
        .update({"nurturing_state": nurturing_state, "temperature": sequence_type, "updated_at": _now().isoformat()})
        .eq("id", lead_id)
        .execute()
    )
    logger.info("[nurturing] lead %s routed to %s (BANT=%d)", lead_id, sequence_type, bant_score)
    return {"lead_id": lead_id, "action": f"routed_to_{sequence_type}", "sequence_type": sequence_type}


async def process_nurturing_queue() -> dict:
    now = _now()
    res = await asyncio.to_thread(
        lambda: supabase.table("leads")
        .select("id, name, business_name, phone, nurturing_state, temperature")
        .not_.is_("nurturing_state", "null")
        .not_.in_("status", ["cliente", "fechado", "perdido"])
        .execute()
    )
    leads = res.data or []
    processed = sent = archived = errors = 0

    for lead in leads:
        state = lead.get("nurturing_state")
        if not state or not isinstance(state, dict):
            continue
        next_send_str = state.get("next_send_at")
        if not next_send_str:
            continue
        try:
            next_send = datetime.fromisoformat(next_send_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if next_send > now:
            continue

        seq_type = state.get("sequence_type", "cold")
        step = state.get("current_step", 0)
        sequence = WARM_SEQUENCE if seq_type == "warm" else COLD_SEQUENCE
        if step >= len(sequence):
            continue

        step_def = sequence[step]
        lead_id = lead["id"]
        name = ((lead.get("name") or lead.get("business_name") or "").split() or ["prezado"])[0]

        try:
            if step_def["message"] is None:
                await asyncio.to_thread(
                    lambda lid=lead_id: supabase.table("leads")
                    .update({"status": "perdido", "loss_reason": "nurturing_expired", "updated_at": now.isoformat()})
                    .eq("id", lid).execute()
                )
                archived += 1
            else:
                message = step_def["message"].format(name=name)
                phone = "".join(c for c in (lead.get("phone") or "") if c.isdigit())
                if phone:
                    from runtime.integrations.zapi import send_text
                    await asyncio.to_thread(lambda: send_text(phone, message))
                    sent += 1

            next_step = step + 1
            next_send_at = (now + timedelta(days=sequence[next_step]["day"] - step_def["day"])).isoformat() if next_step < len(sequence) else None
            new_state = {**state, "current_step": next_step, "next_send_at": next_send_at, "last_sent_at": now.isoformat()}
            await asyncio.to_thread(
                lambda lid=lead_id, ns=new_state: supabase.table("leads")
                .update({"nurturing_state": ns, "updated_at": now.isoformat()})
                .eq("id", lid).execute()
            )
            processed += 1
        except Exception as e:
            logger.error("[nurturing] error lead %s step %d: %s", lead_id, step, e)
            errors += 1

    logger.info("[nurturing] processed=%d sent=%d archived=%d errors=%d", processed, sent, archived, errors)
    return {"processed": processed, "sent": sent, "archived": archived, "errors": errors}


async def handle_temperature_change(lead_id: str, old_temp: str, new_temp: str) -> dict:
    if old_temp == "warm" and new_temp == "hot":
        lead_res = await asyncio.to_thread(
            lambda: supabase.table("leads").select("name, business_name").eq("id", lead_id).maybe_single().execute()
        )
        lead = lead_res.data if lead_res and hasattr(lead_res, "data") else lead_res
        name = (lead.get("name") or lead.get("business_name") or lead_id) if lead else lead_id
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday", "client_id": settings.sparkle_internal_client_id,
                "task_type": "friday_alert",
                "payload": {"alert": "lead_temperature_change", "lead_id": lead_id, "lead_name": name,
                            "message": f"Lead {name} esquentou! Era WARM, agora e HOT. Proposta em 24h."},
                "status": "pending", "priority": 9,
            }).execute()
        )
    if old_temp == "cold" and new_temp == "warm":
        await route_lead_by_temperature(lead_id, 50)
    return {"lead_id": lead_id, "old_temp": old_temp, "new_temp": new_temp, "handled": True}
