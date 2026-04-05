"""
Onboarding service — ONB-1: Pipeline Orquestrador de Onboarding.

Logica de orquestracao central:
- Cria pipeline de fases (onboarding_workflows)
- Idempotencia: detecta onboarding existente por client_name+phone
- Gate check por fase
- Alertas Friday para timeouts
- Notificacoes WhatsApp para cliente em cada transicao de fase
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from runtime.config import settings
from runtime.db import supabase


# ── Constantes ────────────────────────────────────────────────

ONBOARDING_PHASES = [
    "contract",
    "intake",
    "config",
    "test_internal",
    "test_client",
    "go_live",
    "post_go_live",
]

PHASE_MESSAGES = {
    "contract": (
        "Ola {name}! Somos da Sparkle. "
        "Seu contrato e pagamento estao a caminho. "
        "Qualquer duvida, estamos aqui."
    ),
    "intake": (
        "Otimo! Pagamento e contrato confirmados. "
        "Agora vamos conhecer melhor o seu negocio para configurar sua Zenya."
    ),
    "config": (
        "Estamos configurando sua Zenya! "
        "Em breve voce podera testar. "
        "Fique tranquilo, vamos avisar quando estiver pronta."
    ),
    "test_client": (
        "Sua Zenya esta pronta para teste! "
        "Envie uma mensagem para ela e veja como ficou. "
        "Nos diga o que achou."
    ),
}

# Gate conditions per phase
PHASE_CONDITIONS: dict[str, list[str]] = {
    "contract":    ["contract_signed", "payment_confirmed"],
    "intake":      ["intake_complete"],
    "config":      ["brain_ready", "soul_prompt_ready", "kb_ready"],
    "test_internal": ["internal_tests_passed"],
    "test_client": ["client_approved"],
    "go_live":     ["go_live_confirmed"],
    "post_go_live": [],
}

# Next phase mapping
NEXT_PHASE: dict[str, Optional[str]] = {
    "contract":    "intake",
    "intake":      "config",
    "config":      "test_internal",
    "test_internal": "test_client",
    "test_client": "go_live",
    "go_live":     "post_go_live",
    "post_go_live": None,
}


# ── Helpers ───────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _send_whatsapp(phone: Optional[str], message: str) -> None:
    """Send WhatsApp message to client. Silently skips if phone is missing."""
    if not phone:
        print("[onboarding/service] send_whatsapp: phone nao fornecido — skip")
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, phone, message)
        print(f"[onboarding/service] WhatsApp enviado para {phone[:8]}...")
    except Exception as e:
        print(f"[onboarding/service] WARN: falha ao enviar WhatsApp para {phone[:8]}...: {e}")


async def _alert_friday(message: str) -> None:
    """Send Friday alert to Mauro via WhatsApp."""
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        print(f"[onboarding/service] WARN: MAURO_WHATSAPP nao configurado — alerta nao enviado: {message}")
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, f"[Friday] {message}")
    except Exception as e:
        print(f"[onboarding/service] WARN: falha ao alertar Friday: {e}")


# ── Core: Find existing onboarding (idempotency) ─────────────

async def find_existing_onboarding(client_name: str, phone: Optional[str]) -> Optional[dict]:
    """
    Check if an onboarding already exists for this client_name + phone.
    Returns the client row + onboarding_workflows if found.
    """
    try:
        # Search by name + phone in clients
        q = supabase.table("clients").select("id,name,whatsapp,status")
        q = q.ilike("name", client_name)
        if phone:
            q = q.eq("whatsapp", phone)
        result = await asyncio.to_thread(lambda: q.limit(1).execute())
        if not result.data:
            return None

        client = result.data[0]
        client_id = client["id"]

        # Check if onboarding_workflows exist for this client
        wf_result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at")
            .execute()
        )
        workflows = wf_result.data or []

        if not workflows:
            return None

        # Determine current active phase
        current_phase = None
        for wf in workflows:
            if wf.get("status") in ("pending", "in_progress"):
                current_phase = wf.get("phase")
                break

        return {
            "client_id": client_id,
            "client_name": client["name"],
            "status": client.get("status", "onboarding"),
            "current_phase": current_phase or "contract",
            "workflows": workflows,
            "onboarding_id": workflows[0]["id"] if workflows else None,
        }
    except Exception as e:
        print(f"[onboarding/service] find_existing_onboarding error: {e}")
        return None


# ── Core: Create onboarding pipeline ─────────────────────────

async def create_onboarding_pipeline(
    client_name: str,
    business_type: str,
    site_url: Optional[str],
    phone: Optional[str],
    plan: Optional[str],
    mrr_value: Optional[float],
) -> dict:
    """
    AC-2.2: Creates:
    - Record in `clients` (status=onboarding)
    - Record in `zenya_clients` (active=false, testing_mode='off')
    - 7 records in `onboarding_workflows` (one per phase, all status=pending)

    Returns onboarding_id, client_id, status.
    """
    client_id = str(uuid.uuid4())

    # 1. Create client record
    client_row = {
        "id": client_id,
        "name": client_name,
        "niche": business_type,
        "website": site_url or None,
        "whatsapp": phone or None,
        "status": "onboarding",
        "mrr": mrr_value or 0,
        "plan": plan or "essencial",
    }
    await asyncio.to_thread(
        lambda: supabase.table("clients").upsert(client_row, on_conflict="id").execute()
    )

    # 2. Create zenya_clients record (active=false, testing_mode='off' until configured)
    zenya_row = {
        "client_id": client_id,
        "active": False,
        "testing_mode": "off",
    }
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients").upsert(zenya_row, on_conflict="client_id").execute()
        )
    except Exception as e:
        print(f"[onboarding/service] zenya_clients upsert failed (non-fatal): {e}")

    # 3. Create onboarding_sessions record
    session_row = {
        "client_id": client_id,
        "status": "pending",
        "phase": "contract",
        "steps": [],
        "gates_passed": {},
        "phase_history": [],
        "soul_prompt": "",
        "character_slug": "",
        "updated_at": _now(),
    }
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions").upsert(session_row, on_conflict="client_id").execute()
        )
    except Exception as e:
        print(f"[onboarding/service] onboarding_sessions upsert failed (non-fatal): {e}")

    # 4. Create 7 onboarding_workflow rows (one per phase)
    now_ts = _now()
    workflow_rows = []
    for i, phase in enumerate(ONBOARDING_PHASES):
        row = {
            "client_id": client_id,
            "phase": phase,
            "status": "in_progress" if phase == "contract" else "pending",
            "started_at": now_ts if phase == "contract" else None,
            "gate_passed": False,
            "gate_details": {},
        }
        workflow_rows.append(row)

    onboarding_id = None
    try:
        wf_result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows").insert(workflow_rows).execute()
        )
        if wf_result.data:
            # Return id of the first (contract) phase row
            onboarding_id = wf_result.data[0]["id"]
    except Exception as e:
        print(f"[onboarding/service] onboarding_workflows insert failed: {e}")

    # 5. Send initial WhatsApp to client (AC-5.1)
    contract_msg = PHASE_MESSAGES["contract"].format(name=client_name.split()[0])
    await _send_whatsapp(phone, contract_msg)

    return {
        "onboarding_id": onboarding_id,
        "client_id": client_id,
        "status": "contract_pending",
        "phase": "contract",
        "message": f"Pipeline de onboarding criado para '{client_name}'. Fase atual: contrato.",
    }


# ── Gate Check ────────────────────────────────────────────────

async def check_gate(client_id: str, phase: str, conditions: list[str]) -> dict:
    """
    AC-3.2: Verifica se as condicoes do gate para uma fase estao satisfeitas.

    Checks `gate_details` JSONB in onboarding_workflows for the given phase.
    If all conditions are True: marks phase completed, advances to next.
    Returns: { passed: bool, missing: list[str], phase: str }
    """
    # Fetch the workflow row for this phase
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("*")
            .eq("client_id", client_id)
            .eq("phase", phase)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        return {"passed": False, "error": str(e), "missing": conditions}

    wf = result.data if result else None
    if not wf:
        return {
            "passed": False,
            "missing": conditions,
            "error": f"Fase '{phase}' nao encontrada para client_id={client_id}",
        }

    gate_details: dict = wf.get("gate_details") or {}
    missing = [c for c in conditions if not gate_details.get(c, False)]

    if missing:
        return {"passed": False, "missing": missing, "phase": phase}

    # All conditions met — mark phase as completed
    now_ts = _now()
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "status": "completed",
                "gate_passed": True,
                "completed_at": now_ts,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .eq("phase", phase)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/service] gate_check: falha ao atualizar fase '{phase}': {e}")

    # Advance to next phase
    next_phase = NEXT_PHASE.get(phase)
    if next_phase:
        await _advance_to_phase(client_id, next_phase)

    return {
        "passed": True,
        "missing": [],
        "phase": phase,
        "next_phase": next_phase,
        "message": f"Gate '{phase}' passou! Avancando para '{next_phase}'.",
    }


async def _advance_to_phase(client_id: str, phase: str) -> None:
    """Mark a phase as in_progress and send WhatsApp notification."""
    now_ts = _now()
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "status": "in_progress",
                "started_at": now_ts,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .eq("phase", phase)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/service] _advance_to_phase '{phase}' update failed: {e}")

    # Update onboarding_sessions phase
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .update({"phase": phase, "updated_at": now_ts})
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/service] _advance_to_phase sessions update failed (non-fatal): {e}")

    # Send WhatsApp notification for this phase (AC-5.x)
    if phase in PHASE_MESSAGES:
        try:
            client_result = await asyncio.to_thread(
                lambda: supabase.table("clients")
                .select("name,whatsapp")
                .eq("id", client_id)
                .maybe_single()
                .execute()
            )
            client = client_result.data if client_result else None
            if client:
                name = (client.get("name") or "").split()[0]
                phone = client.get("whatsapp")
                msg = PHASE_MESSAGES[phase].format(name=name)
                await _send_whatsapp(phone, msg)
        except Exception as e:
            print(f"[onboarding/service] _advance_to_phase WhatsApp failed (non-fatal): {e}")


# ── Cron: Check all gates in progress ─────────────────────────

async def run_onboarding_gate_check() -> dict:
    """
    AC-4.x: Cron job — verifica todos os onboarding em in_progress.

    - Se gate satisfeito: avanca para proxima fase
    - Se fase em in_progress por > 72h: alerta Friday
    - Se fase em in_progress por > 5 dias: marca stale + alerta Friday
    """
    now = datetime.now(timezone.utc)
    checked = 0
    advanced = 0
    alerts_sent = 0
    stale_marked = 0

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("*")
            .eq("status", "in_progress")
            .execute()
        )
        in_progress = result.data or []
    except Exception as e:
        print(f"[onboarding/cron] falha ao buscar workflows in_progress: {e}")
        return {"error": str(e), "checked": 0}

    for wf in in_progress:
        checked += 1
        client_id = wf["client_id"]
        phase = wf["phase"]
        started_at_raw = wf.get("started_at")

        # Calculate hours elapsed
        hours_elapsed = 0
        if started_at_raw:
            try:
                started_at = datetime.fromisoformat(started_at_raw.replace("Z", "+00:00"))
                hours_elapsed = (now - started_at).total_seconds() / 3600
            except Exception:
                pass

        # Check if stale (> 5 days = 120h)
        if hours_elapsed > 120:
            stale_marked += 1
            try:
                await asyncio.to_thread(
                    lambda cid=client_id, ph=phase: supabase.table("onboarding_workflows")
                    .update({"status": "stale", "updated_at": now.isoformat()})
                    .eq("client_id", cid)
                    .eq("phase", ph)
                    .execute()
                )
            except Exception as e:
                print(f"[onboarding/cron] falha ao marcar stale {client_id}/{phase}: {e}")

            alerts_sent += 1
            await _alert_friday(
                f"[Onboarding] Cliente {client_id[:12]}... esta PARADO na fase '{phase}' "
                f"ha {int(hours_elapsed)}h — marcado como STALE."
            )
            continue

        # Alert if > 72h without progress
        if hours_elapsed > 72:
            alerts_sent += 1
            await _alert_friday(
                f"[Onboarding] Cliente {client_id[:12]}... esta na fase '{phase}' "
                f"ha {int(hours_elapsed)}h sem progresso. Verificar."
            )

        # Try gate check
        conditions = PHASE_CONDITIONS.get(phase, [])
        if not conditions:
            # No conditions needed — auto-advance
            result = await check_gate(client_id, phase, [])
            if result.get("passed"):
                advanced += 1
            continue

        # Check gate conditions
        gate_result = await check_gate(client_id, phase, conditions)
        if gate_result.get("passed"):
            advanced += 1
            print(f"[onboarding/cron] Gate passed: {client_id[:12]}/{phase} -> {gate_result.get('next_phase')}")

    return {
        "checked": checked,
        "advanced": advanced,
        "alerts_sent": alerts_sent,
        "stale_marked": stale_marked,
        "timestamp": now.isoformat(),
    }
