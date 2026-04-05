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
    get_violations_recent,
)

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────

class AdvanceRequest(BaseModel):
    target_step: str | int
    agent: str


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
