"""
Cockpit router — /cockpit/* endpoints.

POST /cockpit/summary  — trigger cockpit summary and send to Mauro via WhatsApp
GET  /cockpit/summary  — generate preview (no send)

Both endpoints work by creating a runtime_task and executing it inline,
following the same pattern used throughout the runtime.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.handlers.cockpit_summary import (
    handle_cockpit_summary,
    handle_cockpit_query,
)

router = APIRouter(prefix="/cockpit", tags=["cockpit"])


@router.post("/summary")
async def trigger_cockpit_summary():
    """
    Trigger a cockpit summary and send to Mauro via WhatsApp.

    Creates a task in runtime_tasks for auditability, then executes inline.
    """
    # Create task record for auditability
    task: dict = {"task_type": "cockpit_summary", "triggered_by": "api"}
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "cockpit_summary",
                "payload": {"triggered_by": "api_manual"},
                "status": "pending",
                "priority": 7,
            }).execute()
        )
        if res.data:
            task = res.data[0]
    except Exception as e:
        print(f"[cockpit_router] failed to create task record: {e}")

    result = await handle_cockpit_summary(task)

    return {
        "status": "sent" if result.get("sent") else "generated",
        "message": result.get("message"),
        "sent_to": settings.mauro_whatsapp if result.get("sent") else None,
    }


@router.get("/summary")
async def preview_cockpit_summary():
    """
    Generate a cockpit summary preview without sending to WhatsApp.
    Useful for testing and dashboards.
    """
    task: dict = {"task_type": "cockpit_query", "triggered_by": "api_preview"}
    result = await handle_cockpit_query(task)

    return {
        "status": "preview",
        "message": result.get("message"),
    }
