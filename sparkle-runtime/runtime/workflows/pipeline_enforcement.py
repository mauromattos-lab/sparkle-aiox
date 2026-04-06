"""
Pipeline Enforcement — C2-B2.

Enforces the AIOS pipeline (story -> @dev -> @qa -> @devops -> done)
by code, not by markdown instructions. No agent can skip steps.

Functions:
  validate_transition(current_step, target_step) -> bool
  record_transition(workflow_run_id, step, agent) -> dict
  check_gates(workflow_run_id, target_step) -> dict
  get_step_name(step_index) -> str
  notify_violation(item_id, current_step, attempted_step, agent) -> None
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)

# ── Step definitions ──────────────────────────────────────────────────

SCHEMA_VERSION = 2  # v2: items com schema_version >= 2 tem enforcement completo

PIPELINE_STEPS: list[dict] = [
    {"step": 0, "name": "prd_approved",    "agent": "@pm"},
    {"step": 1, "name": "spec_approved",   "agent": "@architect"},
    {"step": 2, "name": "stories_ready",   "agent": "@sm"},
    {"step": 3, "name": "dev_complete",    "agent": "@dev"},
    {"step": 4, "name": "qa_approved",     "agent": "@qa"},
    {"step": 5, "name": "po_accepted",     "agent": "@po"},
    {"step": 6, "name": "devops_deployed", "agent": "@devops"},
    {"step": 7, "name": "done",            "agent": "system"},
]

STEP_NAMES: dict[int, str] = {s["step"]: s["name"] for s in PIPELINE_STEPS}
NAME_TO_STEP: dict[str, int] = {s["name"]: s["step"] for s in PIPELINE_STEPS}
MAX_STEP = max(STEP_NAMES.keys())

# Aliases legados — strings v1 continuam funcionando
NAME_TO_STEP.update({
    "story_created":    2,
    "dev_implementing": 3,
    "qa_validating":    4,
    "devops_deploying": 6,
})

# Mapeamento de steps v1 -> v2 para workflow_runs legados
LEGACY_STEP_MAP: dict[int, int] = {
    0: 2,  # story_created     -> stories_ready
    1: 3,  # dev_implementing  -> dev_complete
    2: 4,  # qa_validating     -> qa_approved
    3: 6,  # devops_deploying  -> devops_deployed
    4: 7,  # done              -> done
}

def is_legacy_run(run: dict) -> bool:
    """Detecta se workflow_run foi criado com schema v1 (sem schema_version)."""
    context = run.get("context") or {}
    return context.get("schema_version", 1) < SCHEMA_VERSION

def normalize_step(run: dict) -> int:
    """Retorna o step normalizado para v2, independente do schema do run."""
    current = run.get("current_step", 0)
    if is_legacy_run(run):
        return LEGACY_STEP_MAP.get(current, current)
    return current




# ── Deduplicação de notificações (NFR3) — cache TTL 5 min ────────────

_violation_cache: dict[str, float] = {}

def _should_notify(item_id: str, violation_type: str) -> bool:
    key = f"{item_id}:{violation_type}"
    now = time.time()
    if key in _violation_cache and now - _violation_cache[key] < 300:
        return False
    _violation_cache[key] = now
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core validation ──────────────────────────────────────────────────

def get_step_name(step_index: int) -> str:
    """Return the human-readable name for a step index."""
    return STEP_NAMES.get(step_index, f"unknown_step_{step_index}")


def resolve_step(step_value: int | str) -> int:
    """Resolve a step name or index to the integer index."""
    if isinstance(step_value, int):
        return step_value
    if isinstance(step_value, str):
        if step_value in NAME_TO_STEP:
            return NAME_TO_STEP[step_value]
        try:
            return int(step_value)
        except ValueError:
            pass
    raise ValueError(f"Invalid step: {step_value}")


def validate_transition(current_step: int | str, target_step: int | str) -> bool:
    """
    Validate that a pipeline transition is allowed.
    Only sequential advancement (N -> N+1) is permitted.
    Returns True if valid, False otherwise.
    """
    try:
        current = resolve_step(current_step)
        target = resolve_step(target_step)
    except ValueError:
        return False

    # Only allow advancing by exactly 1 step
    return target == current + 1 and 0 <= target <= MAX_STEP


async def record_transition(
    workflow_run_id: str,
    step: int | str,
    agent: str,
) -> dict:
    """
    Record a pipeline transition in the workflow_runs context.
    Appends to the 'pipeline_history' array in the JSONB context field.
    Updates current_step to the new step.
    Returns the updated workflow_run record.
    """
    step_index = resolve_step(step)
    step_name = get_step_name(step_index)

    # Fetch current workflow_run
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_runs")
        .select("id,current_step,context,status")
        .eq("id", workflow_run_id)
        .single()
        .execute()
    )

    if not result.data:
        raise ValueError(f"workflow_run {workflow_run_id} not found")

    run = result.data
    context = run.get("context") or {}
    history = context.get("pipeline_history", [])

    # Append transition record
    transition_record = {
        "from_step": run.get("current_step", 0),
        "from_step_name": get_step_name(run.get("current_step", 0)),
        "to_step": step_index,
        "to_step_name": step_name,
        "agent": agent,
        "timestamp": _now(),
    }
    history.append(transition_record)
    context["pipeline_history"] = history

    # AC8: garantir schema_version >= 2 em novos runs
    if context.get("schema_version", 1) < SCHEMA_VERSION:
        context["schema_version"] = SCHEMA_VERSION

    # Determine new status
    new_status = "completed" if step_index >= MAX_STEP else "running"

    # Update workflow_run
    update_data = {
        "current_step": step_index,
        "context": context,
        "status": new_status,
        "updated_at": _now(),
    }
    if new_status == "completed":
        update_data["completed_at"] = _now()

    await asyncio.to_thread(
        lambda: supabase.table("workflow_runs")
        .update(update_data)
        .eq("id", workflow_run_id)
        .execute()
    )

    logger.info(
        "[pipeline] transition recorded: run=%s step=%d(%s) agent=%s",
        workflow_run_id, step_index, step_name, agent,
    )

    return {
        "workflow_run_id": workflow_run_id,
        "current_step": step_index,
        "step_name": step_name,
        "agent": agent,
        "status": new_status,
        "history": history,
    }


async def verify_state_persisted(
    sprint_item: str | None,
    step_name: str,
    schema_version: int = 1,
) -> dict:
    """
    Verifica se agent_work_items tem registro verified=True para o sprint_item.
    Para runs legados (schema_version < 2): skip com skipped=True.
    """
    if not sprint_item or schema_version < SCHEMA_VERSION:
        return {"allowed": True, "reason": "legacy_run_skipped", "skipped": True}

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("agent_work_items")
            .select("sprint_item,status,verified,handoff_to,updated_at")
            .eq("sprint_item", sprint_item)
            .single()
            .execute()
        )
    except Exception:
        result = None

    if not result or not result.data:
        return {
            "allowed": False,
            "reason": f"Estado nao persistido. Execute POST /system/state com sprint_item='{sprint_item}' antes de avancar.",
            "error_code": "state_missing",
        }

    record = result.data
    if not record.get("verified", False):
        return {
            "allowed": False,
            "reason": "verified=false em agent_work_items. Confirme a entrega antes de avancar.",
            "error_code": "state_unverified",
        }

    return {"allowed": True, "reason": "State verified", "record": record}


async def check_gates(workflow_run_id: str, target_step: int | str) -> dict:
    """
    Check if a workflow_run can advance to the target step.
    Returns dict with 'allowed' (bool), 'reason' (str), and context info.
    """
    target_index = resolve_step(target_step)
    target_name = get_step_name(target_index)

    # Fetch current state
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_runs")
        .select("id,current_step,context,status")
        .eq("id", workflow_run_id)
        .single()
        .execute()
    )

    if not result.data:
        return {
            "allowed": False,
            "reason": f"workflow_run {workflow_run_id} not found",
            "current_step": None,
            "target_step": target_index,
        }

    run = result.data
    current_step = normalize_step(run)  # AC5: suporte legacy + v2
    current_name = get_step_name(current_step)
    status = run.get("status", "unknown")

    # Check workflow is not completed/cancelled
    if status in ("completed", "cancelled"):
        return {
            "allowed": False,
            "reason": f"Pipeline already {status}",
            "current_step": current_step,
            "current_step_name": current_name,
            "target_step": target_index,
            "target_step_name": target_name,
        }

    # Validate sequential transition
    is_valid = validate_transition(current_step, target_index)

    if is_valid:
        return {
            "allowed": True,
            "reason": "Transition valid",
            "current_step": current_step,
            "current_step_name": current_name,
            "target_step": target_index,
            "target_step_name": target_name,
        }

    # Build violation reason
    if target_index <= current_step:
        reason = f"Cannot go backwards: {current_name} (step {current_step}) -> {target_name} (step {target_index})"
    elif target_index > current_step + 1:
        required_name = get_step_name(current_step + 1)
        reason = f"Step {target_name} requer {required_name} concluido"
    else:
        reason = f"Invalid transition from {current_name} to {target_name}"

    return {
        "allowed": False,
        "reason": reason,
        "current_step": current_step,
        "current_step_name": current_name,
        "target_step": target_index,
        "target_step_name": target_name,
    }


async def notify_violation(
    item_id: str,
    current_step: int,
    attempted_step: int | str,
    agent: str,
    violation_type: str = "gate_skip",  # gate_skip | state_missing | handoff_invalid
) -> None:
    """
    Notify Friday/Mauro about a pipeline violation via proactive WhatsApp.
    Also logs the violation as a runtime_task for audit trail.
    """
    from runtime.friday.proactive import send_proactive
    from runtime.config import settings

    attempted_index = resolve_step(attempted_step)
    current_name = get_step_name(current_step)
    attempted_name = get_step_name(attempted_index)

    if violation_type == "state_missing":
        message = (
            f"Gate bloqueado! Estado nao persistido no Supabase antes do avanco. "
            f"Item {item_id} tentou ir de {current_name} para {attempted_name}. "
            f"Agente: {agent}. Execute POST /system/state antes de avancar."
        )
    elif violation_type == "handoff_invalid":
        message = (
            f"Gate bloqueado! Handoff com campos obrigatorios ausentes. "
            f"Item {item_id} tentou ir de {current_name} para {attempted_name}. "
            f"Agente: {agent}."
        )
    else:
        message = (
            f"Pipeline violation bloqueada! "
            f"Item {item_id} tentou ir de {current_name} (step {current_step}) "
            f"para {attempted_name} (step {attempted_index}). "
            f"Agente: {agent}. Transicao bloqueada."
        )

    # Send proactive WhatsApp notification (com deduplicacao)
    if _should_notify(item_id, violation_type):
        try:
            await send_proactive(message, trigger_type="pipeline_violation")
        except Exception as e:
            logger.error("[pipeline] failed to send violation notification: %s", e)

    # Log violation as runtime_task for audit
    try:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "system",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "pipeline_violation_alert",
                "payload": {
                    "item_id": item_id,
                    "current_step": current_step,
                    "current_step_name": current_name,
                    "attempted_step": attempted_index,
                    "attempted_step_name": attempted_name,
                    "agent": agent,
                    "violation_type": violation_type,
                },
                "status": "done",
                "result": {"message": message, "blocked": True},
                "priority": 9,
            }).execute()
        )
    except Exception as e:
        logger.error("[pipeline] failed to log violation task: %s", e)

    logger.warning(
        "[pipeline] VIOLATION: item=%s agent=%s tried %s->%s (blocked)",
        item_id, agent, current_name, attempted_name,
    )


async def get_violations_recent(hours: int = 24) -> list[dict]:
    """
    Fetch recent pipeline violations from runtime_tasks.
    Returns list of violation records from the last N hours.
    """
    from datetime import timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,payload,result,created_at")
            .eq("task_type", "pipeline_violation_alert")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("[pipeline] failed to fetch violations: %s", e)
        return []
