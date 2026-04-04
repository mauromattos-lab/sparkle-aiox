"""
Content Manager router — endpoints for listing and managing generated content.

GET  /content/list              — lista conteudos gerados recentes
POST /content/{id}/approve      — aprova conteudo (status → approved)
POST /content/{id}/reject       — rejeita conteudo (status → rejected)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase

router = APIRouter()


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
