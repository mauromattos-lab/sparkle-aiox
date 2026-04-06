"""
Onboarding service — ONB-1 + ONB-1.7: Pipeline Orquestrador de Onboarding.

Logica de orquestracao central:
- Cria pipeline de fases (onboarding_workflows)
- Idempotencia: detecta onboarding existente por client_name+phone
- Gate check por fase
- Alertas Friday para timeouts
- Notificacoes WhatsApp para cliente em cada transicao de fase
- ONB-1.7: client_testing_active, periodo de teste, coleta de feedback, loop de ajustes
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
        "business_name": client_name,  # NOT NULL in schema
        "business_type": business_type,
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

    # ONB-2: Auto-trigger intake orchestrator when advancing to 'intake' phase
    if phase == "intake":
        try:
            from runtime.tasks.handlers.intake_orchestrator import handle_intake_orchestrator
            intake_task = {
                "id": f"auto-intake-{client_id}",
                "client_id": client_id,
                "payload": {"client_id": client_id},
            }
            # Fire and forget — intake runs async, does not block phase transition
            asyncio.create_task(handle_intake_orchestrator(intake_task))
            print(f"[onboarding/service] intake orchestrator disparado para {client_id[:12]}...")
        except Exception as e:
            print(f"[onboarding/service] WARN: falha ao disparar intake orchestrator: {e}")

    # ONB-3: Auto-trigger onboard_client_v2 when advancing to 'config' phase
    if phase == "config":
        try:
            from runtime.tasks.handlers.onboard_client_v2 import handle_onboard_client_v2
            config_task = {
                "id": f"auto-config-{client_id}",
                "client_id": client_id,
                "payload": {"client_id": client_id},
            }
            # Fire and forget — config runs async, does not block phase transition
            asyncio.create_task(handle_onboard_client_v2(config_task))
            print(f"[onboarding/service] onboard_client_v2 disparado para {client_id[:12]}...")
        except Exception as e:
            print(f"[onboarding/service] WARN: falha ao disparar onboard_client_v2: {e}")

    # ONB-5: Auto-trigger smoke_test_zenya when advancing to 'test_internal' phase
    if phase == "test_internal":
        try:
            from runtime.tasks.handlers.smoke_test_zenya import handle_smoke_test_zenya
            smoke_task = {
                "id": f"auto-smoke-{client_id}",
                "client_id": client_id,
                "payload": {"client_id": client_id, "retry_count": 0},
            }
            # Fire and forget — smoke test runs async, does not block phase transition
            asyncio.create_task(handle_smoke_test_zenya(smoke_task))
            print(f"[onboarding/service] smoke_test_zenya disparado para {client_id[:12]}...")
        except Exception as e:
            print(f"[onboarding/service] WARN: falha ao disparar smoke_test_zenya: {e}")

    # ONB-1.7 AC-1.1: Notifica Mauro quando pipeline chega em test_client
    # (smoke test PASSOU — gate 3 atingido, aguarda aprovacao de Mauro para liberar cliente)
    if phase == "test_client":
        try:
            # Busca nome do cliente para mensagem contextual
            c_result = await asyncio.to_thread(
                lambda: supabase.table("clients")
                .select("name")
                .eq("id", client_id)
                .maybe_single()
                .execute()
            )
            client_name = (c_result.data or {}).get("name", client_id[:12]) if c_result else client_id[:12]
            await _alert_friday(
                f"[Onboarding] Zenya de {client_name} passou QA interno. "
                f"Pronto para iniciar teste com cliente. "
                f"Confirme via POST /onboarding/{client_id}/approve-client-test ou responda SIM."
            )
        except Exception as e:
            print(f"[onboarding/service] WARN: falha ao alertar Friday sobre test_client: {e}")

    # Story 1.8 AC-1.1: Notifica Mauro quando pipeline chega em go_live
    # (cliente aprovou — gate 4 atingido, aguarda confirmacao explicita de Mauro para go-live)
    if phase == "go_live":
        try:
            c_result = await asyncio.to_thread(
                lambda: supabase.table("clients")
                .select("name")
                .eq("id", client_id)
                .maybe_single()
                .execute()
            )
            client_name = (c_result.data or {}).get("name", client_id[:12]) if c_result else client_id[:12]
            await _alert_friday(
                f"[Onboarding] Zenya de {client_name} esta aprovada pelo cliente e pronta para ir ao ar. "
                f"Confirme o go-live quando estiver pronto: "
                f"responda GOLIVE {client_name.split()[0]} ou acesse POST /onboarding/{client_id}/go-live"
            )
            print(f"[onboarding/service] Friday alertada sobre go_live para {client_id[:12]}...")
        except Exception as e:
            print(f"[onboarding/service] WARN: falha ao alertar Friday sobre go_live: {e}")


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

    # ONB-1.7: Also check client test periods (3d/5d business day alerts)
    try:
        test_period_result = await check_client_test_periods()
        alerts_sent += test_period_result.get("alerted", 0)
    except Exception as e:
        print(f"[onboarding/cron] check_client_test_periods error: {e}")

    # Story 1.8 AC-1.4: Check go_live pending confirmations (daily reminder after 5 days)
    try:
        go_live_reminder_result = await check_go_live_reminders()
        alerts_sent += go_live_reminder_result.get("alerted", 0)
    except Exception as e:
        print(f"[onboarding/cron] check_go_live_reminders error: {e}")

    # ONB-1 AC-6.x: Alertas de timeout por condicao especifica
    try:
        timeout_result = await check_condition_timeouts()
        alerts_sent += timeout_result.get("alerted", 0)
    except Exception as e:
        print(f"[onboarding/cron] check_condition_timeouts error: {e}")

    return {
        "checked": checked,
        "advanced": advanced,
        "alerts_sent": alerts_sent,
        "stale_marked": stale_marked,
        "timestamp": now.isoformat(),
    }


# ── ONB-1.7: Client Testing Mode ─────────────────────────────

def _business_days_elapsed(start_iso: str, now: datetime) -> int:
    """Returns number of business days (Mon-Fri) elapsed since start_iso."""
    from datetime import timedelta
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except Exception:
        return 0
    count = 0
    # Walk day by day from start date to now
    cursor = datetime(start.year, start.month, start.day, tzinfo=start.tzinfo)
    end = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    while cursor < end:
        if cursor.weekday() < 5:  # Mon=0 … Fri=4
            count += 1
        cursor += timedelta(days=1)
    return count


async def _log_onboarding_event(
    client_id: str,
    event_type: str,
    phase: str = "test_client",
    payload: Optional[dict] = None,
) -> None:
    """Insert a row into onboarding_events."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_events").insert({
                "client_id": client_id,
                "event_type": event_type,
                "phase": phase,
                "payload": payload or {},
            }).execute()
        )
    except Exception as e:
        print(f"[onboarding/service] WARN: log_event '{event_type}' failed: {e}")


async def approve_client_test(client_id: str) -> dict:
    """
    ONB-1.7 AC-1.2/1.3/1.4/1.5:
    Mauro aprova inicio do teste com cliente.

    - Busca dados do cliente
    - Ativa client_testing_active=True em zenya_clients
    - Garante testing_mode='client_testing'
    - Salva client_test_started_at no gate_details da fase test_client
    - Envia WhatsApp de boas-vindas ao cliente (numero de teste)
    - Alerta Friday confirmando inicio
    - Insere evento client_test_started em onboarding_events
    """
    # Fetch client info
    try:
        client_result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,whatsapp")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar cliente: {e}"}

    client = client_result.data if client_result else None
    if not client:
        return {"status": "error", "error": f"Cliente {client_id} nao encontrado"}

    client_name = client.get("name", "")
    client_phone = client.get("whatsapp")
    first_name = (client_name.split()[0] if client_name else "Cliente")

    now_ts = _now()

    # AC-1.3: Ativa client_testing_active e garante testing_mode='client_testing'
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({
                "client_testing_active": True,
                "testing_mode": "client_testing",
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/service] approve_client_test: zenya_clients update failed: {e}")

    # AC-1.5: Salva client_test_started_at no gate_details da fase test_client
    try:
        wf_result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("gate_details")
            .eq("client_id", client_id)
            .eq("phase", "test_client")
            .maybe_single()
            .execute()
        )
        current_details: dict = {}
        if wf_result and wf_result.data:
            current_details = wf_result.data.get("gate_details") or {}

        current_details["client_test_started_at"] = now_ts
        current_details.setdefault("adjustment_loops", 0)

        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "gate_details": current_details,
                "status": "in_progress",
                "started_at": now_ts,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .eq("phase", "test_client")
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/service] approve_client_test: gate_details update failed: {e}")

    # AC-1.4: Envia WhatsApp para o cliente
    client_msg = (
        f"Ola {first_name}! Sua Zenya esta pronta para teste. "
        f"Pode conversar com ela neste numero para avaliar. "
        f"Conta pra gente o que achou!"
    )
    await _send_whatsapp(client_phone, client_msg)
    print(f"[onboarding/service] approve_client_test: WhatsApp enviado para {client_name}")

    # Alerta Friday
    await _alert_friday(
        f"[Onboarding] Teste com cliente iniciado para {client_name} ({client_id[:12]}...). "
        f"Periodo: 3-5 dias uteis a partir de agora."
    )

    # Evento
    await _log_onboarding_event(
        client_id,
        "client_test_started",
        payload={"client_name": client_name, "started_at": now_ts},
    )

    return {
        "status": "ok",
        "client_id": client_id,
        "client_testing_active": True,
        "testing_mode": "client_testing",
        "client_test_started_at": now_ts,
        "message": f"Teste com cliente iniciado para {client_name}. Periodo de 3-5 dias uteis.",
    }


async def register_client_feedback(
    client_id: str,
    approved: bool,
    feedback_text: str = "",
) -> dict:
    """
    ONB-1.7 AC-3.x / AC-4.x:
    Registra feedback do cliente apos periodo de teste.

    - Se approved=True: define gate client_approved=True → gate check → avanca para go_live
    - Se approved=False: registra feedback, incrementa adjustment_loops
      - Se loops < 3: volta fase para 'config' (reinicia pipeline)
      - Se loops >= 3: alerta Friday para intervencao manual
    """
    now_ts = _now()

    # Busca gate_details atual da fase test_client
    try:
        wf_result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("gate_details,status")
            .eq("client_id", client_id)
            .eq("phase", "test_client")
            .maybe_single()
            .execute()
        )
    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar workflow: {e}"}

    wf = wf_result.data if wf_result else None
    if not wf:
        return {"status": "error", "error": f"Fase test_client nao encontrada para {client_id}"}

    gate_details: dict = wf.get("gate_details") or {}
    adjustment_loops: int = int(gate_details.get("adjustment_loops", 0))

    if approved:
        # AC-3.2: Gate 4 passa — client_approved=True
        gate_details["client_approved"] = True
        gate_details["client_feedback"] = feedback_text
        gate_details["feedback_registered_at"] = now_ts

        try:
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "gate_details": gate_details,
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .eq("phase", "test_client")
                .execute()
            )
        except Exception as e:
            print(f"[onboarding/service] register_client_feedback: gate_details update failed: {e}")

        # AC-3.5: Evento
        await _log_onboarding_event(
            client_id,
            "client_approved",
            payload={"feedback_text": feedback_text, "approved": True},
        )

        # Dispara gate check — deve avançar para go_live automaticamente
        gate_result = await check_gate(client_id, "test_client", ["client_approved"])

        # AC-1.4 (go_live): Alerta Friday
        await _alert_friday(
            f"[Onboarding] Cliente {client_id[:12]}... APROVOU a Zenya! "
            f"Feedback: '{feedback_text[:100]}'. Gate test_client PASSOU. Avancando para go_live."
        )

        return {
            "status": "ok",
            "approved": True,
            "gate_result": gate_result,
            "message": "Cliente aprovou! Gate test_client passou. Pipeline avancando para go_live.",
        }

    else:
        # AC-3.3 / AC-3.4: Cliente pediu ajustes
        adjustment_loops += 1
        gate_details["adjustment_loops"] = adjustment_loops
        gate_details["client_feedback"] = feedback_text
        gate_details["feedback_registered_at"] = now_ts

        try:
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "gate_details": gate_details,
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .eq("phase", "test_client")
                .execute()
            )
        except Exception as e:
            print(f"[onboarding/service] register_client_feedback: loops update failed: {e}")

        # AC-3.5: Evento
        await _log_onboarding_event(
            client_id,
            "client_requested_adjustments",
            payload={
                "feedback_text": feedback_text,
                "adjustment_loops": adjustment_loops,
            },
        )

        # AC-4.3: Maximo de loops atingido
        if adjustment_loops >= 3:
            await _alert_friday(
                f"[Onboarding] ATENCAO: Cliente {client_id[:12]}... ja passou por 3 rodadas de ajuste "
                f"e ainda nao aprovou. Ultimo feedback: '{feedback_text[:150]}'. "
                f"Intervencao manual necessaria."
            )
            return {
                "status": "max_loops_reached",
                "adjustment_loops": adjustment_loops,
                "message": (
                    "Maximo de 3 loops de ajuste atingido. "
                    "Friday foi alertada para intervencao manual."
                ),
            }

        # AC-4.1: Volta pipeline para fase config (reinicia ONB-3)
        try:
            # Reseta fase test_client para pending
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "status": "pending",
                    "gate_passed": False,
                    "started_at": None,
                    "completed_at": None,
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .eq("phase", "test_client")
                .execute()
            )

            # Reseta fase test_internal para pending
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "status": "pending",
                    "gate_passed": False,
                    "started_at": None,
                    "completed_at": None,
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .eq("phase", "test_internal")
                .execute()
            )

            # Reseta client_testing_active
            await asyncio.to_thread(
                lambda: supabase.table("zenya_clients")
                .update({
                    "client_testing_active": False,
                    "testing_mode": "off",
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .execute()
            )
        except Exception as e:
            print(f"[onboarding/service] register_client_feedback: reset phases failed: {e}")

        # AC-4.1: Alerta Mauro e re-dispara config
        await _alert_friday(
            f"[Onboarding] Cliente {client_id[:12]}... pediu ajustes (loop {adjustment_loops}/3): "
            f"'{feedback_text[:150]}'. Configuracao reiniciada — ONB-3 sera re-executado."
        )

        # Re-avanca para fase config (dispara handle_onboard_client_v2 automaticamente)
        await _advance_to_phase(client_id, "config")

        return {
            "status": "adjustments_requested",
            "adjustment_loops": adjustment_loops,
            "message": (
                f"Ajuste registrado (loop {adjustment_loops}/3). "
                f"Pipeline reiniciado a partir da fase config."
            ),
        }


async def check_client_test_periods() -> dict:
    """
    ONB-1.7 AC-2.1/2.2: Verifica clientes em fase test_client in_progress.

    - Se >= 3 dias uteis sem feedback: alerta Mauro pedindo feedback
    - Se >= 5 dias uteis sem feedback: segundo alerta mais urgente

    Chamado pelo cron onboarding_check_gates (a cada hora).
    """
    now = datetime.now(timezone.utc)
    checked = 0
    alerted = 0

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("client_id,gate_details,started_at")
            .eq("phase", "test_client")
            .eq("status", "in_progress")
            .execute()
        )
        in_progress = result.data or []
    except Exception as e:
        print(f"[onboarding/service] check_client_test_periods: fetch failed: {e}")
        return {"error": str(e), "checked": 0}

    for wf in in_progress:
        checked += 1
        client_id = wf["client_id"]
        gate_details: dict = wf.get("gate_details") or {}

        # Se já foi aprovado, skip
        if gate_details.get("client_approved"):
            continue

        started_at = gate_details.get("client_test_started_at") or wf.get("started_at")
        if not started_at:
            continue

        # Calcula dias uteis decorridos
        bdays = _business_days_elapsed(started_at, now)

        # Busca nome do cliente para alertas mais contextuais
        try:
            c_result = await asyncio.to_thread(
                lambda cid=client_id: supabase.table("clients")
                .select("name")
                .eq("id", cid)
                .maybe_single()
                .execute()
            )
            client_name = (c_result.data or {}).get("name", client_id[:12]) if c_result else client_id[:12]
        except Exception:
            client_name = client_id[:12]

        # AC-2.2: >= 3 dias uteis sem feedback — primeiro alerta
        # AC-2.3: >= 5 dias uteis — segundo alerta mais urgente
        alert_3d_sent = gate_details.get("alert_3d_sent", False)
        alert_5d_sent = gate_details.get("alert_5d_sent", False)

        if bdays >= 5 and not alert_5d_sent:
            alerted += 1
            await _alert_friday(
                f"[Onboarding] URGENTE: {client_name} testou a Zenya por {bdays} dias uteis "
                f"sem dar feedback formal. Pronto para go-live ou deseja mais tempo? "
                f"Responda SIM para go-live ou MAIS TEMPO para estender o periodo."
            )
            gate_details["alert_5d_sent"] = True
            try:
                await asyncio.to_thread(
                    lambda cid=client_id, gd=gate_details: supabase.table("onboarding_workflows")
                    .update({"gate_details": gd, "updated_at": now.isoformat()})
                    .eq("client_id", cid)
                    .eq("phase", "test_client")
                    .execute()
                )
            except Exception as e:
                print(f"[onboarding/service] check_client_test_periods: alert_5d update failed: {e}")

        elif bdays >= 3 and not alert_3d_sent:
            alerted += 1
            await _alert_friday(
                f"[Onboarding] {client_name} testou a Zenya por {bdays} dias uteis. "
                f"Nao houve feedback formal ainda. "
                f"Pronto para go-live ou deseja mais tempo?"
            )
            gate_details["alert_3d_sent"] = True
            try:
                await asyncio.to_thread(
                    lambda cid=client_id, gd=gate_details: supabase.table("onboarding_workflows")
                    .update({"gate_details": gd, "updated_at": now.isoformat()})
                    .eq("client_id", cid)
                    .eq("phase", "test_client")
                    .execute()
                )
            except Exception as e:
                print(f"[onboarding/service] check_client_test_periods: alert_3d update failed: {e}")

    return {"checked": checked, "alerted": alerted, "timestamp": now.isoformat()}


# ── Story 1.8: Go-Live ────────────────────────────────────────

async def pre_go_live_checklist(client_id: str) -> dict:
    """
    Story 1.8 AC-4.1/4.3: Verifica checklist automatico antes do go-live.

    Verifica:
    - zenya_clients.soul_prompt_generated nao esta vazio
    - zenya_knowledge_base tem >= 15 itens ativos para o client_id
    - Gate 4 (client_approved) marcado como True na fase test_client
    - Z-API conectada (Fase 1: log warning apenas, nao bloqueia)

    Retorna:
    {
        can_go_live: bool,
        checks: {
            soul_prompt: bool,
            kb_items: int,
            gate4: bool,
            zapi_connected: "skipped" | bool,
        },
        blocking_issues: list[str]
    }
    """
    checks: dict = {
        "soul_prompt": False,
        "kb_items": 0,
        "gate4": False,
        "zapi_connected": "skipped",  # Fase 1: nao bloqueia
    }
    blocking_issues: list[str] = []

    # 1. Verifica soul_prompt_generated em zenya_clients
    try:
        zc_result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("soul_prompt_generated")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        zc = zc_result.data if zc_result else None
        soul_prompt_val = (zc or {}).get("soul_prompt_generated", "") or ""
        checks["soul_prompt"] = bool(soul_prompt_val.strip())
    except Exception as e:
        print(f"[onboarding/go-live] pre_go_live_checklist: soul_prompt check failed: {e}")

    if not checks["soul_prompt"]:
        blocking_issues.append("soul_prompt_generated esta vazio — execute a configuracao (ONB-3) primeiro")

    # 2. Verifica zenya_knowledge_base (>= 15 itens ativos)
    try:
        kb_result = await asyncio.to_thread(
            lambda: supabase.table("zenya_knowledge_base")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("active", True)
            .execute()
        )
        kb_count = kb_result.count if kb_result and kb_result.count is not None else len(kb_result.data or [])
        checks["kb_items"] = kb_count
    except Exception as e:
        print(f"[onboarding/go-live] pre_go_live_checklist: kb check failed: {e}")
        checks["kb_items"] = 0

    if checks["kb_items"] < 15:
        blocking_issues.append(
            f"zenya_knowledge_base tem apenas {checks['kb_items']} itens ativos — minimo e 15"
        )

    # 3. Verifica Gate 4 (client_approved) em onboarding_workflows fase test_client
    try:
        wf_result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("gate_details,gate_passed")
            .eq("client_id", client_id)
            .eq("phase", "test_client")
            .maybe_single()
            .execute()
        )
        wf = wf_result.data if wf_result else None
        gate_details: dict = (wf or {}).get("gate_details") or {}
        checks["gate4"] = bool(gate_details.get("client_approved", False))
    except Exception as e:
        print(f"[onboarding/go-live] pre_go_live_checklist: gate4 check failed: {e}")

    if not checks["gate4"]:
        blocking_issues.append(
            "Gate 4 nao foi aprovado — cliente ainda nao confirmou a Zenya via /client-feedback"
        )

    # 4. Z-API: Fase 1 — apenas log warning, nao bloqueia
    print(
        f"[onboarding/go-live] WARN: verificacao Z-API nao implementada (Fase 1) "
        f"para client_id={client_id[:12]}..."
    )
    checks["zapi_connected"] = "skipped"

    can_go_live = len(blocking_issues) == 0

    return {
        "can_go_live": can_go_live,
        "checks": checks,
        "blocking_issues": blocking_issues,
    }


async def execute_go_live(client_id: str) -> dict:
    """
    Story 1.8 AC-2.1/2.2/3.x/3.4:
    Executa transicao atomica de testing -> live.

    Sequencia:
    1. zenya_clients.testing_mode = 'live'
    2. zenya_clients.active = True
    3. zenya_clients.client_testing_active = False
    4. onboarding_workflows go_live: status=completed, gate_passed=True
    5. onboarding_workflows post_go_live: status=in_progress (via _advance_to_phase)
    6. clients.status = 'active'

    Em caso de falha: rollback best-effort (restaura testing_mode='client_testing').
    """
    now_ts = _now()
    rollback_needed = False
    rollback_reason = ""

    # Busca dados do cliente para notificacoes
    try:
        client_result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,whatsapp")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar cliente: {e}"}

    client = client_result.data if client_result else None
    if not client:
        return {"status": "error", "error": f"Cliente {client_id} nao encontrado"}

    client_name = client.get("name", "")
    client_phone = client.get("whatsapp")
    first_name = (client_name.split()[0] if client_name else "Cliente")

    # ── Passo 1-3: Atualiza zenya_clients ────────────────────────
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({
                "testing_mode": "live",
                "active": True,
                "client_testing_active": False,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .execute()
        )
        print(f"[onboarding/go-live] zenya_clients atualizado para LIVE: {client_id[:12]}...")
    except Exception as e:
        return {
            "status": "error",
            "error": f"Falha ao atualizar zenya_clients: {e}",
            "rollback": "nao necessario — nada foi alterado",
        }

    # ── Passo 4: Marca fase go_live como completed ────────────────
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
            .eq("phase", "go_live")
            .execute()
        )
        print(f"[onboarding/go-live] fase go_live marcada completed: {client_id[:12]}...")
    except Exception as e:
        rollback_needed = True
        rollback_reason = f"Falha ao completar fase go_live: {e}"

    # ── Passo 5: Avanca para post_go_live ─────────────────────────
    if not rollback_needed:
        try:
            await _advance_to_phase(client_id, "post_go_live")
            print(f"[onboarding/go-live] fase post_go_live iniciada: {client_id[:12]}...")
        except Exception as e:
            # post_go_live start failure — nao critico, log e continua
            print(f"[onboarding/go-live] WARN: falha ao iniciar post_go_live: {e}")

    # ── Passo 6: Atualiza clients.status = 'active' ───────────────
    if not rollback_needed:
        try:
            await asyncio.to_thread(
                lambda: supabase.table("clients")
                .update({"status": "active"})
                .eq("id", client_id)
                .execute()
            )
            print(f"[onboarding/go-live] clients.status=active: {client_id[:12]}...")
        except Exception as e:
            # Non-fatal — clients table update failure should not block go-live
            print(f"[onboarding/go-live] WARN: falha ao atualizar clients.status (non-fatal): {e}")

    # ── Rollback best-effort se falhou ────────────────────────────
    if rollback_needed:
        print(f"[onboarding/go-live] ROLLBACK: {rollback_reason}")
        try:
            await asyncio.to_thread(
                lambda: supabase.table("zenya_clients")
                .update({
                    "testing_mode": "client_testing",
                    "active": False,
                    "client_testing_active": True,
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .execute()
            )
            print(f"[onboarding/go-live] ROLLBACK executado: testing_mode restaurado para client_testing")
        except Exception as rb_e:
            print(f"[onboarding/go-live] ERRO CRITICO: rollback falhou: {rb_e}")

        await _alert_friday(
            f"[Onboarding] ERRO no go-live de {client_name}: {rollback_reason}. "
            f"Estado revertido para client_testing. Verificar manualmente."
        )
        return {
            "status": "error",
            "error": rollback_reason,
            "rollback": "executado — testing_mode restaurado para client_testing",
        }

    # ── AC-3.3: Evento go_live em onboarding_events ───────────────
    await _log_onboarding_event(
        client_id,
        "go_live",
        phase="go_live",
        payload={
            "client_id": client_id,
            "event": "activated",
            "go_live_at": now_ts,
            "activated_by": "mauro",
        },
    )

    # ── AC-3.1: Notifica Friday/Mauro ─────────────────────────────
    await _alert_friday(
        f"[Onboarding] Zenya de {client_name} esta LIVE! "
        f"Monitoramento pos-go-live iniciado."
    )

    # ── AC-3.2: Notifica cliente via WhatsApp ─────────────────────
    client_msg = (
        f"Oi {first_name}! Sua Zenya esta oficialmente no ar! "
        f"Seus clientes ja podem falar com ela. "
        f"Qualquer duvida, estamos aqui."
    )
    await _send_whatsapp(client_phone, client_msg)

    print(f"[onboarding/go-live] GO-LIVE CONCLUIDO para {client_name} ({client_id[:12]}...)")

    return {
        "status": "live",
        "client_id": client_id,
        "client_name": client_name,
        "go_live_at": now_ts,
        "activated_by": "mauro",
        "message": f"Zenya de {client_name} esta LIVE! Pos-go-live iniciado.",
    }


async def check_go_live_reminders() -> dict:
    """
    Story 1.8 AC-1.4: Verifica clientes aguardando confirmacao de go-live.

    - Se fase go_live in_progress por > 5 dias sem confirmar:
      envia lembrete diario para Mauro (1 por dia, idempotente via go_live_reminder_sent_at)

    Chamado pelo cron run_onboarding_gate_check (a cada hora).
    """
    now = datetime.now(timezone.utc)
    checked = 0
    alerted = 0

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("client_id,gate_details,started_at")
            .eq("phase", "go_live")
            .eq("status", "in_progress")
            .execute()
        )
        in_progress = result.data or []
    except Exception as e:
        print(f"[onboarding/service] check_go_live_reminders: fetch failed: {e}")
        return {"error": str(e), "checked": 0, "alerted": 0}

    for wf in in_progress:
        checked += 1
        client_id = wf["client_id"]
        gate_details: dict = wf.get("gate_details") or {}

        started_at_raw = gate_details.get("go_live_started_at") or wf.get("started_at")
        if not started_at_raw:
            continue

        # Calcula dias calendar decorridos desde que fase go_live iniciou
        try:
            started_at = datetime.fromisoformat(started_at_raw.replace("Z", "+00:00"))
            days_elapsed = (now - started_at).days
        except Exception:
            continue

        # Apenas se > 5 dias sem confirmacao
        if days_elapsed <= 5:
            continue

        # Idempotencia: 1 lembrete por dia via go_live_reminder_sent_at
        reminder_sent_at_raw = gate_details.get("go_live_reminder_sent_at")
        if reminder_sent_at_raw:
            try:
                reminder_sent_at = datetime.fromisoformat(
                    reminder_sent_at_raw.replace("Z", "+00:00")
                )
                hours_since_reminder = (now - reminder_sent_at).total_seconds() / 3600
                if hours_since_reminder < 20:  # menos de ~1 dia
                    continue
            except Exception:
                pass

        # Busca nome do cliente
        try:
            c_result = await asyncio.to_thread(
                lambda cid=client_id: supabase.table("clients")
                .select("name")
                .eq("id", cid)
                .maybe_single()
                .execute()
            )
            client_name = (c_result.data or {}).get("name", client_id[:12]) if c_result else client_id[:12]
        except Exception:
            client_name = client_id[:12]

        # Envia lembrete
        alerted += 1
        await _alert_friday(
            f"[Onboarding] Go-live de {client_name} aguardando sua confirmacao ha {days_elapsed} dias. "
            f"Confirme via POST /onboarding/{client_id}/go-live quando estiver pronto."
        )

        # Salva timestamp do lembrete para idempotencia
        gate_details["go_live_reminder_sent_at"] = now.isoformat()
        try:
            await asyncio.to_thread(
                lambda cid=client_id, gd=dict(gate_details): supabase.table("onboarding_workflows")
                .update({"gate_details": gd, "updated_at": now.isoformat()})
                .eq("client_id", cid)
                .eq("phase", "go_live")
                .execute()
            )
        except Exception as e:
            print(f"[onboarding/service] check_go_live_reminders: gate_details update failed: {e}")

    return {"checked": checked, "alerted": alerted, "timestamp": now.isoformat()}


# ── ONB-1 AC-6.x: Timeout por condição específica ────────────

def _hours_since(started_at_iso: str, now: datetime) -> float:
    """Returns hours elapsed since started_at_iso (ISO 8601 string)."""
    try:
        started_at = datetime.fromisoformat(started_at_iso.replace("Z", "+00:00"))
        return (now - started_at).total_seconds() / 3600
    except Exception:
        return 0.0


async def _get_client_name(client_id: str) -> str:
    """Returns the client's name, falling back to the first 12 chars of client_id."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("name")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        return (result.data or {}).get("name", client_id[:12]) if result else client_id[:12]
    except Exception:
        return client_id[:12]


async def _update_gate_details(client_id: str, phase: str, gate_details: dict) -> None:
    """Persists gate_details back to onboarding_workflows for the given client+phase."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "gate_details": gate_details,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("client_id", client_id)
            .eq("phase", phase)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/service] _update_gate_details {client_id[:12]}/{phase} failed: {e}")


async def check_condition_timeouts() -> dict:
    """
    ONB-1 AC-6.1/6.2/6.3: Alertas de timeout por condicao especifica.

    - AC-6.1: contrato nao assinado em 48h (fase contract, sem contract_signed)
    - AC-6.2: pagamento nao confirmado em 72h (fase contract, sem payment_confirmed)
    - AC-6.3: intake parado por 5+ dias uteis (fase intake)

    Idempotente via flags no gate_details de cada workflow.
    Chamado pelo cron run_onboarding_gate_check.
    """
    now = datetime.now(timezone.utc)
    alerted = 0

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("client_id,phase,gate_details,started_at")
            .eq("status", "in_progress")
            .execute()
        )
    except Exception as e:
        print(f"[onboarding/cron] check_condition_timeouts: fetch failed: {e}")
        return {"error": str(e), "alerted": 0}

    for wf in (result.data or []):
        client_id = wf["client_id"]
        phase = wf["phase"]
        gate_details: dict = wf.get("gate_details") or {}
        started_at = wf.get("started_at")

        if not started_at:
            continue

        hours = _hours_since(started_at, now)
        client_name = await _get_client_name(client_id)

        if phase == "contract":
            # AC-6.1: contract_signed nao aparece em 48h
            if (
                hours >= 48
                and not gate_details.get("contract_signed")
                and not gate_details.get("alert_contract_48h_sent")
            ):
                await _alert_friday(
                    f"[Onboarding] {client_name} — contrato nao foi assinado em 48h. "
                    f"Verificar se cliente recebeu o link."
                )
                gate_details["alert_contract_48h_sent"] = True
                await _update_gate_details(client_id, phase, gate_details)
                alerted += 1

            # AC-6.2: payment_confirmed nao aparece em 72h
            if (
                hours >= 72
                and not gate_details.get("payment_confirmed")
                and not gate_details.get("alert_payment_72h_sent")
            ):
                await _alert_friday(
                    f"[Onboarding] {client_name} — pagamento nao confirmado em 72h. "
                    f"Verificar cobranca Asaas."
                )
                gate_details["alert_payment_72h_sent"] = True
                await _update_gate_details(client_id, phase, gate_details)
                alerted += 1

        elif phase == "intake":
            # AC-6.3: intake parado por 5+ dias uteis
            bdays = _business_days_elapsed(started_at, now)
            if bdays >= 5 and not gate_details.get("alert_intake_5d_sent"):
                await _alert_friday(
                    f"[Onboarding] {client_name} — intake parado ha {bdays} dias uteis. "
                    f"Cliente pode nao ter respondido o formulario."
                )
                gate_details["alert_intake_5d_sent"] = True
                await _update_gate_details(client_id, phase, gate_details)
                alerted += 1

    return {"alerted": alerted}


# ── LIFECYCLE-1.4: Milestone & TTV Tracking ──────────────────

MILESTONE_TYPES = frozenset([
    'zenya_active',
    'first_real_message',
    'first_week_report',
    'aha_moment_30d',
])


async def track_milestone(
    client_id: str,
    milestone_type: str,
    metadata: Optional[dict] = None,
) -> dict:
    '''
    LIFECYCLE-1.4: Track a client milestone.

    Upserts into client_milestones (UNIQUE on client_id + milestone_type).
    Calling twice for the same type updates metadata but never duplicates.

    milestone_type: zenya_active | first_real_message | first_week_report | aha_moment_30d

    If milestone_type == first_real_message:
      - Fetches zenya_clients.created_at (contract date proxy)
      - Calculates TTV = days between created_at and now()
      - Stores in ttv_days field

    Sends congratulations WhatsApp (to Mauro via Friday) for:
      - zenya_active
      - first_real_message
    '''
    if milestone_type not in MILESTONE_TYPES:
        raise ValueError(
            f'milestone_type invalido: {milestone_type!r}. '
            f'Validos: {sorted(MILESTONE_TYPES)}'
        )

    now_ts = _now()
    ttv_days: Optional[int] = None
    business_name: str = client_id  # fallback

    # Fetch zenya_clients row — try client_id column first, then UUID PK (BUG-3 fix)
    try:
        zc_result = await asyncio.to_thread(
            lambda: supabase.table('zenya_clients')
            .select('id,business_name,created_at')
            .eq('client_id', client_id)
            .maybe_single()
            .execute()
        )
        zc_data = zc_result.data if zc_result else None
        if not zc_data:
            # Fallback: try by UUID PK (zenya_clients.id)
            zc_result2 = await asyncio.to_thread(
                lambda: supabase.table('zenya_clients')
                .select('id,business_name,created_at')
                .eq('id', client_id)
                .maybe_single()
                .execute()
            )
            zc_data = zc_result2.data if zc_result2 else None
        if not zc_data:
            raise ValueError(f'Cliente nao encontrado em zenya_clients: {client_id}')
        business_name = zc_data.get('business_name') or client_id
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f'Falha ao buscar zenya_clients para {client_id}: {e}') from e

    # Calculate TTV for first_real_message
    if milestone_type == 'first_real_message':
        try:
            raw_created_at = zc_data.get('created_at')
            if raw_created_at:
                if isinstance(raw_created_at, str):
                    raw = raw_created_at.replace('Z', '+00:00')
                    created_at_dt = datetime.fromisoformat(raw)
                    if created_at_dt.tzinfo is None:
                        created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                else:
                    created_at_dt = raw_created_at
                now_dt = datetime.now(timezone.utc)
                ttv_days = (now_dt - created_at_dt).days
        except Exception as e:
            print(f'[milestone] WARN: falha ao calcular TTV para {client_id}: {e}')
            ttv_days = None

    # Build upsert row — client_milestones.client_id FK references zenya_clients.id (not zenya_clients.client_id)
    zc_id = zc_data.get('id') or client_id  # zenya_clients PK
    milestone_row: dict = {
        'client_id': zc_id,
        'milestone_type': milestone_type,
        'achieved_at': now_ts,
        'metadata': metadata or {},
    }
    if ttv_days is not None:
        milestone_row['ttv_days'] = ttv_days

    # Upsert — UNIQUE(client_id, milestone_type) prevents duplicates
    try:
        await asyncio.to_thread(
            lambda: supabase.table('client_milestones')
            .upsert(milestone_row, on_conflict='client_id,milestone_type')
            .execute()
        )
    except Exception as e:
        raise RuntimeError(f'Falha ao upsert client_milestones: {e}') from e

    print(f'[milestone] {milestone_type} registrado para {client_id[:12]}... ({business_name})')

    # Send congratulations via Friday (Mauro WhatsApp) for key milestones
    if milestone_type == 'zenya_active':
        msg = (
            '🎉 *Go-Live confirmado!*\n\n'
            f'A Zenya de {business_name} esta ativa e respondendo!\n'
            'Primeiro marco alcancado. 🚀'
        )
        await _alert_friday(msg)

    elif milestone_type == 'first_real_message':
        ttv_str = f'{ttv_days} dias' if ttv_days is not None else 'N/A'
        msg = (
            '🎯 *Primeiro contato real!*\n\n'
            f'{business_name} recebeu a primeira mensagem real de um cliente.\n'
            f'TTV: {ttv_str} do contrato ao primeiro uso real.'
        )
        await _alert_friday(msg)

    return {
        'status': 'ok',
        'client_id': client_id,
        'milestone_type': milestone_type,
        'achieved_at': now_ts,
        'ttv_days': ttv_days,
        'business_name': business_name,
    }


async def get_client_milestones(client_id: str) -> list:
    '''
    LIFECYCLE-1.4: Fetch all milestones for a client, ordered by achieved_at.
    client_id here is zenya_clients.client_id — we translate to zenya_clients.id for the FK.
    Returns empty list if none found (milestones are optional).
    '''
    try:
        # Translate zenya_clients.client_id -> zenya_clients.id (FK used in client_milestones)
        zc_result = await asyncio.to_thread(
            lambda: supabase.table('zenya_clients')
            .select('id')
            .eq('client_id', client_id)
            .maybe_single()
            .execute()
        )
        zc_data = zc_result.data if zc_result else None
        if not zc_data:
            return []
        zc_id = zc_data['id']
        result = await asyncio.to_thread(
            lambda: supabase.table('client_milestones')
            .select('milestone_type,achieved_at,ttv_days,metadata')
            .eq('client_id', zc_id)
            .order('achieved_at')
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f'[milestone] WARN: falha ao buscar milestones para {client_id}: {e}')
        return []
