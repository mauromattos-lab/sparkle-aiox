"""
SYS-5: Observer API — endpoint para consultar gaps pendentes e metricas do Observer.
Complementa gaps/router.py com visao operacional (gaps por tipo, implementacoes automaticas).
B2-06: Quality endpoints — query quality logs and per-agent summaries.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query

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


# ── Quality Log Endpoints (B2-06) ─────────────────────────────


@router.get("/quality")
async def quality_logs(
    agent: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=1),
    max_score: Optional[float] = Query(None, ge=0, le=1),
    limit: int = Query(50, ge=1, le=500),
):
    """Query quality evaluation logs with optional filters."""
    query = (
        supabase.table("response_quality_log")
        .select("id,agent_slug,user_message_preview,response_preview,score,scores_detail,issues,suggestion,evaluated_at")
        .order("evaluated_at", desc=True)
    )
    if agent:
        query = query.eq("agent_slug", agent)
    if min_score is not None:
        query = query.gte("score", min_score)
    if max_score is not None:
        query = query.lte("score", max_score)

    result = await asyncio.to_thread(lambda: query.limit(limit).execute())
    logs = result.data or []

    return {
        "logs": logs,
        "count": len(logs),
        "filters": {"agent": agent, "min_score": min_score, "max_score": max_score},
    }


@router.get("/quality/summary")
async def quality_summary():
    """Per-agent quality summary: averages, worst performers, recent trend."""
    result = await asyncio.to_thread(
        lambda: supabase.table("response_quality_log")
        .select("agent_slug,score,evaluated_at")
        .order("evaluated_at", desc=True)
        .limit(1000)
        .execute()
    )
    logs = result.data or []

    if not logs:
        return {"total_evaluations": 0, "agents": {}, "worst_performers": [], "recent_avg": None}

    # Aggregate per agent
    agent_data: dict[str, list[float]] = {}
    for log in logs:
        slug = log.get("agent_slug", "unknown")
        score = log.get("score", 0.5)
        agent_data.setdefault(slug, []).append(score)

    agents_summary = {}
    for slug, scores in agent_data.items():
        agents_summary[slug] = {
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
        }

    # Worst performers (lowest average, min 3 evaluations)
    worst = sorted(
        [(slug, info) for slug, info in agents_summary.items() if info["count"] >= 3],
        key=lambda x: x[1]["avg_score"],
    )[:5]
    worst_performers = [{"agent": slug, **info} for slug, info in worst]

    # Recent trend (last 50 vs previous 50)
    all_scores = [log.get("score", 0.5) for log in logs]
    recent_50 = all_scores[:50]
    previous_50 = all_scores[50:100]
    recent_avg = round(sum(recent_50) / len(recent_50), 3) if recent_50 else None
    previous_avg = round(sum(previous_50) / len(previous_50), 3) if previous_50 else None

    return {
        "total_evaluations": len(logs),
        "agents": agents_summary,
        "worst_performers": worst_performers,
        "recent_avg": recent_avg,
        "previous_avg": previous_avg,
        "trend": (
            "improving" if recent_avg and previous_avg and recent_avg > previous_avg
            else "declining" if recent_avg and previous_avg and recent_avg < previous_avg
            else "stable"
        ),
    }
