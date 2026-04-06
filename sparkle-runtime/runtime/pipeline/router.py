"""
Pipeline Enforcement API — C2-B2.

Endpoints:
  GET  /pipeline/status/{item_id}   — current step, step name, history
  POST /pipeline/advance/{item_id}  — validate and advance pipeline step
  GET  /pipeline/violations         — recent violations (last 24h)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.workflows.pipeline_enforcement import (
    STEP_NAMES,
    NAME_TO_STEP,
    get_step_name,
    resolve_step,
    validate_transition,
    record_transition,
    check_gates,
    notify_violation,
    verify_state_persisted,
    get_violations_recent,
    SCHEMA_VERSION,
)
from runtime.pipeline.handoff_validator import (
    HandoffPayload,
    validate_handoff,
    store_handoff,
    consume_handoff,
    REQUIRED_FIELDS,
)

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────

class AdvanceRequest(BaseModel):
    target_step: str | int
    agent: str
    handoff_validation_id: Optional[str] = None  # obrigatorio para schema_version >= 2


# ── GET /pipeline/status/{item_id} ───────────────────────────────────

@router.get("/status/{item_id}")
async def pipeline_status(item_id: str):
    """
    Returns the current pipeline status for a work item.
    Looks up the workflow_run linked to this item (workflow_type='aios_pipeline').
    """
    # Find workflow_run for this item
    run = await _get_pipeline_run(item_id)

    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"No aios_pipeline workflow_run found for item '{item_id}'",
        )

    current_step = run.get("current_step", 0)
    context = run.get("context") or {}
    history = context.get("pipeline_history", [])

    return {
        "item_id": item_id,
        "workflow_run_id": run["id"],
        "current_step": current_step,
        "step_name": get_step_name(current_step),
        "status": run.get("status", "unknown"),
        "total_steps": len(STEP_NAMES),
        "steps": [
            {"step": idx, "name": name, "completed": idx <= current_step}
            for idx, name in sorted(STEP_NAMES.items())
        ],
        "history": history,
    }


# ── POST /pipeline/advance/{item_id} ────────────────────────────────

@router.post("/advance/{item_id}")
async def pipeline_advance(item_id: str, req: AdvanceRequest):
    """
    Advance the pipeline for a work item to the target step.
    Validates that the transition is sequential (no skipping).
    Returns HTTP 422 on invalid transitions with a clear error message.
    """
    # Resolve target step
    try:
        target_index = resolve_step(req.target_step)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_step",
                "message": f"Step '{req.target_step}' is not a valid pipeline step",
                "valid_steps": list(STEP_NAMES.values()),
            },
        )

    # Find workflow_run for this item
    run = await _get_pipeline_run(item_id)

    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"No aios_pipeline workflow_run found for item '{item_id}'",
        )

    workflow_run_id = run["id"]
    current_step = run.get("current_step", 0)

    # Check gates
    gate_result = await check_gates(workflow_run_id, target_index)

    if not gate_result["allowed"]:
        # Record violation and notify
        await notify_violation(
            item_id=item_id,
            current_step=current_step,
            attempted_step=target_index,
            agent=req.agent,
        )

        target_name = get_step_name(target_index)
        current_name = get_step_name(current_step)

        raise HTTPException(
            status_code=422,
            detail={
                "error": "pipeline_violation",
                "message": gate_result["reason"],
                "current_step": current_name,
                "attempted_step": target_name,
                "agent": req.agent,
            },
        )

    # [AC7] Verificar state persistence (Story 1.2)
    sprint_item = (run.get("context") or {}).get("sprint_item")
    schema_ver = (run.get("context") or {}).get("schema_version", 1)
    current_step_name = get_step_name(current_step)
    state_result = await verify_state_persisted(sprint_item, current_step_name, schema_ver)

    if not state_result["allowed"]:
        await notify_violation(
            item_id=item_id,
            current_step=current_step,
            attempted_step=target_index,
            agent=req.agent,
            violation_type="state_missing",
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error": state_result["error_code"],
                "message": state_result["reason"],
                "sprint_item": sprint_item,
                "action_required": f"POST /system/state com sprint_item={sprint_item!r} e verified=true",
            },
        )

    # [AC6] Handoff validation (Story 1.3)
    if schema_ver >= SCHEMA_VERSION and not req.handoff_validation_id:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "handoff_required",
                "message": "handoff_validation_id obrigatorio. Execute POST /pipeline/validate-handoff primeiro.",
                "action_required": "POST /pipeline/validate-handoff",
            }
        )

    if req.handoff_validation_id:
        consume_result = await consume_handoff(req.handoff_validation_id)
        if not consume_result["allowed"]:
            raise HTTPException(
                status_code=422,
                detail={"error": "handoff_consumed", "message": consume_result["reason"]}
            )

    # Advance pipeline
    result = await record_transition(
        workflow_run_id=workflow_run_id,
        step=target_index,
        agent=req.agent,
    )

    return {
        "item_id": item_id,
        **result,
    }


# ── GET /pipeline/violations ──────────────────────────────────────────

@router.get("/violations")
async def pipeline_violations(hours: int = 24):
    """
    Returns recent pipeline violations (last N hours, default 24).
    """
    violations = await get_violations_recent(hours=hours)

    return {
        "violations": violations,
        "count": len(violations),
        "hours": hours,
    }


# ── Helper ────────────────────────────────────────────────────────────


# ── POST /pipeline/validate-handoff ──────────────────────────────────

@router.post("/validate-handoff")
async def pipeline_validate_handoff(payload: HandoffPayload):
    """
    Valida o bloco de handoff do processo v2.
    Retorna handoff_validation_id se valido.
    """
    valid, errors = validate_handoff(payload)

    if not valid:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "handoff_invalid",
                "valid": False,
                "errors": errors,
                "missing_or_invalid_fields": [e.split(":")[0] for e in errors],
                "required_fields": REQUIRED_FIELDS,
            }
        )

    validation_id = await store_handoff(payload)

    return {
        "valid": True,
        "handoff_validation_id": validation_id,
        "sprint_item": payload.sprint_item,
        "proximo": payload.proximo,
        "message": "Handoff valido. Use handoff_validation_id no POST /pipeline/advance.",
    }


async def _get_pipeline_run(item_id: str) -> dict | None:
    """
    Find the aios_pipeline workflow_run linked to a work item.
    Searches by:
      1. workflow_runs with context->>'item_id' matching
      2. workflow_runs with context->>'sprint_item' matching
      3. Direct ID match (if item_id is a workflow_run_id)
    """
    # Strategy 1: context contains item_id
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("workflow_runs")
            .select("*")
            .eq("workflow_type", "aios_pipeline")
            .limit(50)
            .execute()
        )
        runs = result.data or []
        for run in runs:
            ctx = run.get("context") or {}
            if ctx.get("item_id") == item_id or ctx.get("sprint_item") == item_id:
                return run
    except Exception:
        pass

    # Strategy 2: direct workflow_run_id match
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("workflow_runs")
            .select("*")
            .eq("id", item_id)
            .eq("workflow_type", "aios_pipeline")
            .single()
            .execute()
        )
        if result.data:
            return result.data
    except Exception:
        pass

    return None


# ============================================================================
# LIFECYCLE-2.3 — Conversion Tracking endpoints
# ============================================================================

from typing import Optional as _Optional

from runtime.pipeline.conversion import (
    record_proposal_sent as _record_proposal_sent,
    record_first_response as _record_first_response,
    record_contract_signed as _record_contract_signed,
    get_conversion_metrics as _get_conversion_metrics,
    check_stale_proposals as _check_stale_proposals,
)


# ── POST /pipeline/leads/{lead_id}/proposal-sent ─────────────────────

@router.post("/leads/{lead_id}/proposal-sent")
async def pipeline_proposal_sent(lead_id: str):
    """
    LIFECYCLE-2.3: Record when a proposal was sent to a lead.
    Sets proposal_sent=true, proposal_sent_at=now(), increments touchpoints_count.
    Idempotent: safe to call multiple times (timestamp only set on first call).
    """
    try:
        result = await _record_proposal_sent(lead_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error recording proposal: {exc}")


# ── POST /pipeline/leads/{lead_id}/response ──────────────────────────

@router.post("/leads/{lead_id}/response")
async def pipeline_first_response(lead_id: str):
    """
    LIFECYCLE-2.3: Record first response from lead after proposal.
    Sets first_response_at=now(), advances status to negotiation.
    Idempotent: safe to call multiple times.
    """
    try:
        result = await _record_first_response(lead_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error recording response: {exc}")


# ── GET /pipeline/conversion-metrics ────────────────────────────────

@router.get("/conversion-metrics")
async def pipeline_conversion_metrics(
    period: str = "30d",
    channel: _Optional[str] = None,
):
    """
    LIFECYCLE-2.3: Aggregate conversion metrics with optional filters.

    Query params:
      period:  7d | 30d | 90d | all  (default: 30d)
      channel: filter by channel_source (instagram, whatsapp, indicacao, ...)

    Response format:
      {period, total_proposals, converted, lost, active,
       conversion_rate, avg_time_to_convert_days,
       avg_time_to_first_response_days, by_channel}
    """
    valid_periods = {"7d", "30d", "90d", "all"}
    if period not in valid_periods:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid period '{period}'. Valid: {sorted(valid_periods)}",
        )
    try:
        metrics = await _get_conversion_metrics(period=period, channel=channel)
        return metrics
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error computing metrics: {exc}")


# ── GET /pipeline/stale-proposals ────────────────────────────────────

@router.get("/stale-proposals")
async def pipeline_stale_proposals(days: int = 7):
    """
    LIFECYCLE-2.3: List proposals with no response for >= days days.
    Default: 7 days. Returns leads enriched with days_since_proposal.
    """
    if days < 1:
        raise HTTPException(status_code=422, detail="days must be >= 1")
    try:
        stale = await _check_stale_proposals(stale_days=days)
        return {
            "stale_proposals": stale,
            "count": len(stale),
            "threshold_days": days,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error fetching stale proposals: {exc}")


# ── LIFECYCLE-2.2: Nurturing endpoints ────────────────────

from runtime.pipeline.nurturing import (
    route_lead_by_temperature,
    process_nurturing_queue,
    handle_temperature_change,
)


@router.post("/leads/{lead_id}/nurture")
async def pipeline_nurture_lead(lead_id: str, bant_score: int = 50):
    """LIFECYCLE-2.2: Route lead to nurturing sequence based on BANT score."""
    try:
        result = await route_lead_by_temperature(lead_id, bant_score)
        return {"status": "ok", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Nurturing failed: {exc}")


@router.get("/nurturing/queue")
async def pipeline_nurturing_queue():
    """LIFECYCLE-2.2: Show pending nurturing messages."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("leads")
            .select("id, name, business_name, temperature, nurturing_state, status")
            .not_.is_("nurturing_state", "null")
            .not_.in_("status", ["cliente", "fechado", "perdido"])
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = res.data or []
        return {"queue": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Queue fetch failed: {exc}")


@router.post("/nurturing/process")
async def pipeline_process_nurturing():
    """LIFECYCLE-2.2: Force process nurturing queue (testing)."""
    try:
        result = await process_nurturing_queue()
        return {"status": "ok", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Process failed: {exc}")
