"""
SYS-5: Observer API — endpoint para consultar gaps pendentes e metricas do Observer.
Complementa gaps/router.py com visao operacional (gaps por tipo, implementacoes automaticas).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter

from runtime.db import supabase

router = APIRouter()


@router.get("/gaps")
async def observer_gaps(
    status: Optional[str] = "pending",
    gap_type: Optional[str] = None,
    limit: int = 50,
):
    """Lista gaps detectados pelo Observer com filtros.
    Diferente de /system/gaps: foco operacional, inclui implementation_result."""
    query = (
        supabase.table("gap_reports")
        .select("id,report_type,summary,severity,status,details,implementation_result,created_at,updated_at")
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    if gap_type:
        query = query.eq("report_type", gap_type)

    result = await asyncio.to_thread(lambda: query.limit(limit).execute())
    gaps = result.data or []

    return {
        "gaps": gaps,
        "count": len(gaps),
        "filters": {"status": status, "gap_type": gap_type},
    }


@router.get("/summary")
async def observer_summary():
    """Resumo do Observer: gaps por status, implementacoes recentes, saude."""
    result = await asyncio.to_thread(
        lambda: supabase.table("gap_reports")
        .select("report_type,status,severity")
        .execute()
    )
    gaps = result.data or []

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for g in gaps:
        s = g.get("status", "unknown")
        t = g.get("report_type", "unknown")
        sev = g.get("severity", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "total_gaps": len(gaps),
        "by_status": by_status,
        "by_type": by_type,
        "by_severity": by_severity,
        "pending_action": by_status.get("pending", 0) + by_status.get("approved", 0),
    }
