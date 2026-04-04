"""
Content Manager router v2 — endpoints for listing, scheduling, and managing generated content.

v1 endpoints (preserved):
  GET  /content/list              — lista conteudos gerados recentes
  GET  /content/calendar          — conteudo organizado por data (calendar view)
  POST /content/schedule          — agenda geracao de conteudo para data futura
  POST /content/{id}/approve      — aprova conteudo (status -> approved)
  POST /content/{id}/reject       — rejeita conteudo (status -> rejected)

v2 endpoints (new):
  GET  /content/templates         — lista templates disponiveis por formato/plataforma
  GET  /content/{id}/preview      — preview estruturado do conteudo para plataforma-alvo
  POST /content/generate-batch    — geracao em lote (plano semanal multi-plataforma)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.config import settings
from runtime.content.models import (
    BatchGenerateRequest,
    ContentFormat,
    ContentPreview,
    Platform,
    PLATFORM_METADATA,
    ScheduleRequest,
    get_platform_constraints,
    validate_format_for_platform,
)
from runtime.content.templates import get_template, list_templates, get_prompt_instructions
from runtime.db import supabase

router = APIRouter()


# ── v1 Pydantic models (kept for backward compat) ────────────

class ScheduleRequestV1(BaseModel):
    """v1 schedule request — still accepted, maps to v2 internally."""
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
    platform: Optional[str] = None,
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
    if platform:
        query = query.eq("platform", platform)

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


# ── POST /content/schedule ────────────────────────────────────

@router.post("/schedule")
async def schedule_content(req: ScheduleRequest):
    """
    Queue content generation for a future date.
    Creates a runtime_task with task_type=generate_content and scheduled_for.
    Accepts v2 fields (platform, ContentFormat enum) natively.
    """
    # Validate format is supported on the target platform
    if not validate_format_for_platform(req.format, req.platform):
        raise HTTPException(
            status_code=400,
            detail=f"Format '{req.format.value}' is not supported on platform '{req.platform.value}'",
        )

    try:
        scheduled_iso = req.scheduled_for.isoformat()
        result = (
            supabase
            .table("runtime_tasks")
            .insert({
                "agent_id": "content-engine",
                "client_id": req.client_id or settings.sparkle_internal_client_id,
                "task_type": "generate_content",
                "payload": {
                    "triggered_by": "schedule_endpoint",
                    "topic": req.topic,
                    "format": req.format.value,
                    "platform": req.platform.value,
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
        "format": req.format.value,
        "platform": req.platform.value,
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
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()

    # 1. Fetch generated content from the period
    try:
        query = (
            supabase
            .table("generated_content")
            .select("id, client_id, persona, format, platform, topic, status, source_type, created_at")
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
            "format": payload.get("format", "post"),
            "platform": payload.get("platform", "instagram"),
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


# ══════════════════════════════════════════════════════════════
# v2 ENDPOINTS
# ══════════════════════════════════════════════════════════════

# ── GET /content/templates ────────────────────────────────────

@router.get("/templates")
async def get_content_templates(
    platform: Optional[str] = None,
    format: Optional[str] = None,
):
    """
    List available content templates with their structure and constraints.
    Filter by platform and/or format.
    """
    templates = list_templates()

    if platform:
        templates = [t for t in templates if t["platform"] == platform]
    if format:
        templates = [t for t in templates if t["format"] == format]

    return {
        "templates": templates,
        "count": len(templates),
        "platforms": [p.value for p in Platform],
        "formats": [f.value for f in ContentFormat],
    }


# ── GET /content/{id}/preview ─────────────────────────────────

@router.get("/{content_id}/preview")
async def preview_content(content_id: str):
    """
    Return a structured preview of a content item formatted for its target platform.
    Includes platform-specific metadata (aspect ratio, duration limits, hashtag strategy).
    """
    try:
        result = (
            supabase
            .table("generated_content")
            .select("*")
            .eq("id", content_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Content not found")

    item = result.data[0]

    # Resolve platform (default to instagram for v1 content)
    platform_str = item.get("platform") or "instagram"
    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.INSTAGRAM

    # Resolve format
    format_str = item.get("format") or "post"
    # Map v1 format names
    v1_map = {"instagram_post": "post"}
    format_str = v1_map.get(format_str, format_str)
    try:
        fmt = ContentFormat(format_str)
    except ValueError:
        fmt = ContentFormat.POST

    # Get platform constraints
    constraints = get_platform_constraints(fmt, platform)

    # Get template info
    template = get_template(fmt, platform)
    template_info = template.to_dict() if template else None

    # Build preview text based on format
    content = item.get("content") or ""
    hashtags = item.get("hashtags") or []
    preview_text = _build_preview_text(content, hashtags, fmt, platform)

    return {
        "id": content_id,
        "platform": platform.value,
        "format": fmt.value,
        "persona": item.get("persona", "zenya"),
        "topic": item.get("topic", ""),
        "content": content,
        "hashtags": hashtags,
        "status": item.get("status", "draft"),
        "created_at": item.get("created_at"),
        "platform_metadata": {
            "constraints": constraints,
            "template": template_info,
        },
        "preview_text": preview_text,
        "char_count": len(content),
        "hashtag_count": len(hashtags),
    }


# ── POST /content/generate-batch ──────────────────────────────

@router.post("/generate-batch")
async def generate_batch(req: BatchGenerateRequest):
    """
    Generate multiple content items at once from a week/multi-day plan.
    Creates one runtime_task per item, all with status=pending.
    Returns the list of created task IDs.
    """
    client_id = req.client_id or settings.sparkle_internal_client_id
    created_tasks: list[dict] = []
    errors: list[dict] = []

    for day in req.days:
        for idx, item in enumerate(day.items):
            # Validate format+platform combo
            if not validate_format_for_platform(item.format, item.platform):
                errors.append({
                    "date": day.date,
                    "index": idx,
                    "topic": item.topic,
                    "error": f"Format '{item.format.value}' not supported on '{item.platform.value}'",
                })
                continue

            # Create a scheduled task for each item
            # Schedule at 10:00 BRT (13:00 UTC) by default for the target date
            scheduled_iso = f"{day.date}T13:00:00+00:00"

            try:
                result = (
                    supabase
                    .table("runtime_tasks")
                    .insert({
                        "agent_id": "content-engine",
                        "client_id": client_id,
                        "task_type": "generate_content",
                        "payload": {
                            "triggered_by": "batch_endpoint",
                            "topic": item.topic,
                            "format": item.format.value,
                            "platform": item.platform.value,
                            "persona": item.persona,
                            "source_type": "batch",
                            "scheduled_for": scheduled_iso,
                            "batch_date": day.date,
                        },
                        "status": "pending",
                        "priority": 5,
                        "scheduled_for": scheduled_iso,
                    })
                    .execute()
                )
                if result.data:
                    task = result.data[0]
                    created_tasks.append({
                        "task_id": task.get("id"),
                        "date": day.date,
                        "topic": item.topic,
                        "format": item.format.value,
                        "platform": item.platform.value,
                        "persona": item.persona,
                    })
            except Exception as exc:
                errors.append({
                    "date": day.date,
                    "index": idx,
                    "topic": item.topic,
                    "error": str(exc),
                })

    return {
        "message": f"Batch created: {len(created_tasks)} tasks scheduled, {len(errors)} errors",
        "tasks": created_tasks,
        "errors": errors,
        "total_scheduled": len(created_tasks),
        "total_errors": len(errors),
    }


# ── Helpers ──────────────────────────────────────────────────

def _build_preview_text(
    content: str,
    hashtags: list[str],
    fmt: ContentFormat,
    platform: Platform,
) -> str:
    """Build a human-readable preview string for a content item."""
    meta = PLATFORM_METADATA.get(platform, {})
    max_caption = meta.get("max_caption_length", 2200)

    lines: list[str] = []

    # Header
    lines.append(f"--- {platform.value.upper()} | {fmt.value.upper()} ---")
    lines.append("")

    # Truncate content for preview if too long
    if len(content) > 500:
        preview_content = content[:500] + "..."
    else:
        preview_content = content

    lines.append(preview_content)

    # Hashtags
    if hashtags:
        hashtag_strategy = meta.get("hashtag_strategy", {})
        max_tags = hashtag_strategy.get("recommended", 10)
        tags_to_show = hashtags[:max_tags]
        lines.append("")
        lines.append(" ".join(f"#{h}" for h in tags_to_show))
        if len(hashtags) > max_tags:
            lines.append(f"  (+{len(hashtags) - max_tags} mais)")

    # Character count warning
    if len(content) > max_caption:
        lines.append("")
        lines.append(f"[AVISO: {len(content)} chars — excede limite de {max_caption}]")

    return "\n".join(lines)
