"""
Content Manager router — endpoints for listing and managing generated content.

GET  /content/list              — lista conteudos gerados recentes
GET  /content/calendar          — conteudo organizado por data (calendar view)
POST /content/schedule          — agenda geração de conteudo para data futura
POST /content/{id}/approve      — aprova conteudo (status → approved)
POST /content/{id}/reject       — rejeita conteudo (status → rejected)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.config import settings
from runtime.db import supabase

router = APIRouter()


# ── Pydantic models ──────────────────────────────────────────

class ScheduleRequest(BaseModel):
    topic: str
    persona: str = "zenya"
    format: str = "instagram_post"
    scheduled_for: datetime


# ── GET /content/list ─────────────────────────────────────────

@router.get("/list")
async def list_content(
    limit: int = 20,
    status: Optional[str] = None,
    client_id: Optional[str] = None,
):
    """Return recent generated content, newest first."""
    query = (
        supabase
        .table("generated_content")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )

    if status:
        query = query.eq("status", status)
    if client_id:
        query = query.eq("client_id", client_id)

    try:
        result = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"items": result.data, "count": len(result.data)}


# ── POST /content/{id}/approve ────────────────────────────────

@router.post("/{content_id}/approve")
async def approve_content(content_id: str):
    """Set content status to approved."""
    try:
        result = (
            supabase
            .table("generated_content")
            .update({
                "status": "approved",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", content_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Content not found")

    return {"status": "approved", "id": content_id}


# ── POST /content/{id}/reject ─────────────────────────────────

@router.post("/{content_id}/reject")
async def reject_content(content_id: str):
    """Set content status to rejected."""
    try:
        result = (
            supabase
            .table("generated_content")
            .update({
                "status": "rejected",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", content_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Content not found")

    return {"status": "rejected", "id": content_id}


# ── POST /content/schedule ───────────────────────────────────

@router.post("/schedule")
async def schedule_content(req: ScheduleRequest):
    """
    Queue content generation for a future date.
    Creates a runtime_task with task_type=generate_content and scheduled_for.
    """
    try:
        scheduled_iso = req.scheduled_for.isoformat()
        result = (
            supabase
            .table("runtime_tasks")
            .insert({
                "agent_id": "content-engine",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "generate_content",
                "payload": {
                    "triggered_by": "schedule_endpoint",
                    "topic": req.topic,
                    "format": req.format,
                    "persona": req.persona,
                    "source_type": "scheduled",
                    "scheduled_for": scheduled_iso,
                },
                "status": "pending",
                "priority": 4,
                "scheduled_for": scheduled_iso,
            })
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create scheduled task")

    task = result.data[0]
    return {
        "message": "Content generation scheduled",
        "task_id": task["id"],
        "scheduled_for": scheduled_iso,
        "topic": req.topic,
        "format": req.format,
        "persona": req.persona,
    }


# ── GET /content/calendar ────────────────────────────────────

@router.get("/calendar")
async def content_calendar(
    days: int = 30,
    client_id: Optional[str] = None,
):
    """
    Return content organized by date for a calendar/timeline view.
    Groups generated_content by created_at date and includes
    pending scheduled tasks from runtime_tasks.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()

    # 1. Fetch generated content from the period
    try:
        query = (
            supabase
            .table("generated_content")
            .select("id, client_id, persona, format, topic, status, source_type, created_at")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(200)
        )
        if client_id:
            query = query.eq("client_id", client_id)
        content_res = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # 2. Fetch pending scheduled tasks (generate_content with scheduled_for)
    try:
        sched_query = (
            supabase
            .table("runtime_tasks")
            .select("id, payload, status, scheduled_for, created_at")
            .eq("task_type", "generate_content")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(50)
        )
        sched_res = sched_query.execute()
    except Exception:
        sched_res = type("R", (), {"data": []})()

    # 3. Group content by date
    by_date: dict[str, dict] = {}

    for item in (content_res.data or []):
        date_key = (item.get("created_at") or "")[:10]  # YYYY-MM-DD
        if not date_key:
            continue
        if date_key not in by_date:
            by_date[date_key] = {"date": date_key, "content": [], "scheduled": []}
        by_date[date_key]["content"].append(item)

    # Add scheduled tasks
    for task in (sched_res.data or []):
        payload = task.get("payload") or {}
        sched_for = payload.get("scheduled_for") or task.get("scheduled_for") or ""
        date_key = sched_for[:10] if sched_for else (task.get("created_at") or "")[:10]
        if not date_key:
            continue
        if date_key not in by_date:
            by_date[date_key] = {"date": date_key, "content": [], "scheduled": []}
        by_date[date_key]["scheduled"].append({
            "task_id": task["id"],
            "topic": payload.get("topic", ""),
            "format": payload.get("format", "instagram_post"),
            "persona": payload.get("persona", "zenya"),
            "scheduled_for": sched_for,
            "status": task["status"],
        })

    # Sort by date descending
    calendar = sorted(by_date.values(), key=lambda d: d["date"], reverse=True)

    return {
        "days": days,
        "total_content": len(content_res.data or []),
        "total_scheduled": len(sched_res.data or []),
        "calendar": calendar,
    }
