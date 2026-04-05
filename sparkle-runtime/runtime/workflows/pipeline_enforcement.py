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
from datetime import datetime, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)

# ── Step definitions ──────────────────────────────────────────────────

PIPELINE_STEPS: list[dict] = [
    {"step": 0, "name": "story_created",     "agent": "@architect/@pm"},
    {"step": 1, "name": "dev_implementing",   "agent": "@dev"},
    {"step": 2, "name": "qa_validating",      "agent": "@qa"},
    {"step": 3, "name": "devops_deploying",   "agent": "@devops"},
    {"step": 4, "name": "done",               "agent": "system"},
]

STEP_NAMES: dict[int, str] = {s["step"]: s["name"] for s in PIPELINE_STEPS}
NAME_TO_STEP: dict[str, int] = {s["name"]: s["step"] for s in PIPELINE_STEPS}
MAX_STEP = max(STEP_NAMES.keys())


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
    current_step = run.get("current_step", 0)
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

    message = (
        f"Pipeline violation bloqueada! "
        f"Item {item_id} tentou ir de {current_name} (step {current_step}) "
        f"para {attempted_name} (step {attempted_index}). "
        f"Agente: {agent}. Transicao bloqueada."
    )

    # Send proactive WhatsApp notification
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
                    "violation_type": "step_skip",
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
