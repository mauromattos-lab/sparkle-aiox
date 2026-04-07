"""
SYS-5: Gap Reports API — endpoints para consultar, aprovar e rejeitar gaps.
Alternativa REST ao fluxo de aprovacao via WhatsApp.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from runtime.config import settings
from runtime.db import supabase

router = APIRouter()


class ApproveRequest(BaseModel):
    approved_by: str = "mauro"


# ── Endpoints ────────────────────────────────────────────────


@router.get("")
async def list_gaps(status: Optional[str] = None, report_type: Optional[str] = None):
    """Lista gap_reports com filtros opcionais."""
    query = supabase.table("gap_reports").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if report_type:
        query = query.eq("report_type", report_type)
    result = await asyncio.to_thread(lambda: query.limit(50).execute())
    return {"gaps": result.data or [], "count": len(result.data or [])}


@router.post("/{gap_id}/approve")
async def approve_gap(gap_id: str, body: ApproveRequest):
    """Aprova um gap e cria task auto_implement_gap."""
    now = datetime.now(timezone.utc).isoformat()
    await asyncio.to_thread(
        lambda: supabase.table("gap_reports")
        .update({
            "status": "approved",
            "approved_by": body.approved_by,
            "approved_at": now,
            "updated_at": now,
        })
        .eq("id", gap_id)
        .execute()
    )

    # Criar task para implementacao automatica
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "system",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "auto_implement_gap",
            "payload": {"gap_id": gap_id},
            "status": "pending",
            "priority": 6,
        }).execute()
    )

    return {"message": f"Gap {gap_id} aprovado", "implementation_scheduled": True}


@router.post("/{gap_id}/reject")
async def reject_gap(gap_id: str):
    """Rejeita um gap."""
    now = datetime.now(timezone.utc).isoformat()
    await asyncio.to_thread(
        lambda: supabase.table("gap_reports")
        .update({"status": "rejected", "updated_at": now})
        .eq("id", gap_id)
        .execute()
    )
    return {"message": f"Gap {gap_id} rejeitado"}


@router.get("/stats")
async def gap_stats():
    """Metricas: gaps por tipo, por status, total."""
    result = await asyncio.to_thread(
        lambda: supabase.table("gap_reports")
        .select("report_type,status,severity")
        .execute()
    )
    gaps = result.data or []

    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for g in gaps:
        t = g.get("report_type", "unknown")
        s = g.get("status", "unknown")
        sev = g.get("severity", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "total": len(gaps),
        "by_type": by_type,
        "by_status": by_status,
        "by_severity": by_severity,
    }
