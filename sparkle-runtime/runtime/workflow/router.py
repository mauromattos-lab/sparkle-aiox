"""
Workflow Engine router — endpoints para gerenciar workflows declarativos.

Endpoints:
  POST /workflow/start                    — cria instancia + dispara primeiro step
  GET  /workflow/instances                — lista instancias (filtro por status, client_id)
  GET  /workflow/instances/:id            — detalhe com step atual e context
  POST /workflow/instances/:id/pause      — pausa workflow
  POST /workflow/instances/:id/resume     — retoma (cria task para current_step)
  POST /workflow/instances/:id/cancel     — cancela workflow
  GET  /workflow/templates                — lista templates ativos
  GET  /workflow/templates/:slug          — detalhe de um template
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Request models ──────────────────────────────────────────────────

class WorkflowStartRequest(BaseModel):
    template_slug: str
    name: str
    client_id: Optional[str] = None
    context: dict = {}


# ── POST /workflow/start ────────────────────────────────────────────

@router.post("/start")
async def start_workflow(req: WorkflowStartRequest):
    """
    Cria uma instancia de workflow a partir de um template e dispara o primeiro step.
    """
    # 1. Validate template exists and is active
    template_result = await asyncio.to_thread(
        lambda: supabase.table("workflow_templates")
        .select("*")
        .eq("slug", req.template_slug)
        .eq("active", True)
        .limit(1)
        .execute()
    )

    if not template_result.data:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{req.template_slug}' nao encontrado ou inativo",
        )

    template = template_result.data[0]
    steps = template.get("steps", [])

    if not steps:
        raise HTTPException(
            status_code=400,
            detail=f"Template '{req.template_slug}' nao tem steps definidos",
        )

    # 2. Create workflow instance
    insert_data = {
        "template_id": template["id"],
        "template_slug": req.template_slug,
        "name": req.name,
        "current_step": 0,
        "status": "running",
        "context": req.context,
        "started_by": "api",
    }
    # Only include client_id if a valid UUID was provided (column is nullable)
    if req.client_id:
        insert_data["client_id"] = req.client_id

    instance_result = await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .insert(insert_data)
        .execute()
    )

    if not instance_result.data:
        raise HTTPException(status_code=500, detail="Falha ao criar instancia de workflow")

    instance = instance_result.data[0]
    instance_id = instance["id"]

    # 3. Create first task (workflow_step with step_index=0)
    task_insert = {
        "agent_id": "system",
        "task_type": "workflow_step",
        "payload": {
            "workflow_instance_id": instance_id,
            "step_index": 0,
        },
        "status": "pending",
        "priority": template.get("default_priority", 7),
    }
    if req.client_id:
        task_insert["client_id"] = req.client_id

    task_result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .insert(task_insert)
        .execute()
    )

    task_id = task_result.data[0]["id"] if task_result.data else None

    print(f"[workflow] started: slug={req.template_slug} instance={instance_id} first_task={task_id}")

    return {
        "instance_id": instance_id,
        "template_slug": req.template_slug,
        "name": req.name,
        "status": "running",
        "first_task_id": task_id,
        "total_steps": len(steps),
    }


# ── GET /workflow/instances ─────────────────────────────────────────

@router.get("/instances")
async def list_instances(status: Optional[str] = None, client_id: Optional[str] = None):
    """Lista instancias de workflow com filtros opcionais."""
    query = supabase.table("workflow_instances").select("*")

    if status:
        query = query.eq("status", status)
    if client_id:
        query = query.eq("client_id", client_id)

    query = query.order("created_at", desc=True).limit(50)

    result = await asyncio.to_thread(lambda: query.execute())
    return {"instances": result.data or [], "count": len(result.data or [])}


# ── GET /workflow/instances/:id ─────────────────────────────────────

@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    """Detalhe de uma instancia com step atual, context acumulado e template info."""
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .select("*")
        .eq("id", instance_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Instancia nao encontrada")

    instance = result.data

    # Fetch template for step details
    template_result = await asyncio.to_thread(
        lambda: supabase.table("workflow_templates")
        .select("slug,name,steps")
        .eq("id", instance["template_id"])
        .single()
        .execute()
    )

    template = template_result.data if template_result.data else {}
    steps = template.get("steps", [])
    current_step_index = instance.get("current_step", 0)
    current_step_info = steps[current_step_index] if current_step_index < len(steps) else None

    return {
        **instance,
        "template_name": template.get("name"),
        "total_steps": len(steps),
        "current_step_info": current_step_info,
    }


# ── POST /workflow/instances/:id/pause ──────────────────────────────

@router.post("/instances/{instance_id}/pause")
async def pause_instance(instance_id: str):
    """Pausa uma instancia de workflow (status='paused')."""
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .select("status")
        .eq("id", instance_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Instancia nao encontrada")

    if result.data["status"] != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Instancia esta '{result.data['status']}' — so pode pausar instancias 'running'",
        )

    await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .update({"status": "paused", "updated_at": _now()})
        .eq("id", instance_id)
        .execute()
    )

    return {"instance_id": instance_id, "status": "paused"}


# ── POST /workflow/instances/:id/resume ─────────────────────────────

@router.post("/instances/{instance_id}/resume")
async def resume_instance(instance_id: str):
    """
    Retoma uma instancia pausada: muda status para 'running'
    e cria task para o current_step.
    """
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .select("*")
        .eq("id", instance_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Instancia nao encontrada")

    instance = result.data

    if instance["status"] != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Instancia esta '{instance['status']}' — so pode retomar instancias 'paused'",
        )

    # Update status to running
    await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .update({"status": "running", "updated_at": _now()})
        .eq("id", instance_id)
        .execute()
    )

    # Create task for current_step
    current_step = instance.get("current_step", 0)

    resume_task_insert = {
        "agent_id": "system",
        "task_type": "workflow_step",
        "payload": {
            "workflow_instance_id": instance_id,
            "step_index": current_step,
        },
        "status": "pending",
        "priority": 7,
    }
    if instance.get("client_id"):
        resume_task_insert["client_id"] = instance["client_id"]

    task_result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .insert(resume_task_insert)
        .execute()
    )

    task_id = task_result.data[0]["id"] if task_result.data else None

    return {
        "instance_id": instance_id,
        "status": "running",
        "resumed_at_step": current_step,
        "task_id": task_id,
    }


# ── POST /workflow/instances/:id/cancel ─────────────────────────────

@router.post("/instances/{instance_id}/cancel")
async def cancel_instance(instance_id: str):
    """Cancela uma instancia de workflow."""
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .select("status")
        .eq("id", instance_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Instancia nao encontrada")

    if result.data["status"] in ("completed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Instancia ja esta '{result.data['status']}'",
        )

    await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .update({
            "status": "cancelled",
            "completed_at": _now(),
            "updated_at": _now(),
        })
        .eq("id", instance_id)
        .execute()
    )

    return {"instance_id": instance_id, "status": "cancelled"}


# ── GET /workflow/templates ─────────────────────────────────────────

@router.get("/templates")
async def list_templates(active_only: bool = True):
    """Lista templates de workflow."""
    query = supabase.table("workflow_templates").select("id,slug,name,description,default_priority,active,version,created_at")

    if active_only:
        query = query.eq("active", True)

    query = query.order("slug")

    result = await asyncio.to_thread(lambda: query.execute())
    return {"templates": result.data or [], "count": len(result.data or [])}


# ── GET /workflow/templates/definitions ────────────────────────────
# NOTE: must be registered BEFORE /templates/{slug} to avoid path capture

@router.get("/templates/definitions/all")
async def list_template_definitions():
    """
    Returns in-code template definitions (no DB roundtrip).
    Useful for documentation, validation, and seeing what seed_workflow_templates will create.
    """
    from runtime.workflows.templates import get_template_definitions
    definitions = get_template_definitions()
    return {"definitions": definitions, "count": len(definitions)}


# ── POST /workflow/templates/seed ──────────────────────────────────

@router.post("/templates/seed")
async def seed_templates():
    """
    Upsert workflow templates from code into Supabase.
    Uses slug as unique key — updates existing (if version is higher), inserts new.
    Safe to call multiple times (idempotent).
    """
    from runtime.workflows.templates import seed_workflow_templates
    result = await seed_workflow_templates()
    return result


# ── GET /workflow/templates/:slug ───────────────────────────────────

@router.get("/templates/{slug}")
async def get_template(slug: str):
    """Detalhe de um template de workflow incluindo todos os steps."""
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_templates")
        .select("*")
        .eq("slug", slug)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Template '{slug}' nao encontrado")

    template = result.data
    steps = template.get("steps", [])

    return {
        **template,
        "total_steps": len(steps),
    }
