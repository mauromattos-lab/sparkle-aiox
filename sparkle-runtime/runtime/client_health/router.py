"""
Client Health router — /health/* endpoints.

GET  /health/all               — all clients current scores
GET  /health/{client_id}       — current score + signals for one client
POST /health/recalculate       — force recalculate all clients
GET  /health/{client_id}/history — score history with pagination
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from runtime.client_health.calculator import (
    calculate_health_score,
    calculate_all_health_scores,
    get_health_score,
    get_health_history,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── GET /health/all ───────────────────────────────────────


@router.get("/all")
async def list_all_health_scores():
    """
    Retorna o Health Score mais recente de todos os clientes Zenya ativos,
    buscando do banco (sem recalcular).

    Para forçar recalculo, use POST /health/recalculate.
    """
    from runtime.db import supabase
    import asyncio

    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_health")
            .select("client_id, score, classification, signals, calculated_at")
            .order("calculated_at", desc=True)
            .execute()
        )
        rows = res.data or []

        # Deduplica: mantém apenas o score mais recente por client_id
        seen: set[str] = set()
        latest: list[dict] = []
        for row in rows:
            cid = str(row.get("client_id", ""))
            if cid not in seen:
                seen.add(cid)
                latest.append(row)

        return {"scores": latest, "count": len(latest)}
    except Exception as e:
        logger.error("[health/router] list_all_health_scores error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch health scores: {e}")


# ── GET /health/{client_id} ───────────────────────────────


@router.get("/{client_id}")
async def get_client_health(client_id: str):
    """
    Retorna o Health Score mais recente de um cliente.
    Busca do banco — não recalcula.
    """
    result = await get_health_score(client_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No health score found for client {client_id}. Run POST /health/recalculate first.",
        )
    return result


# ── POST /health/recalculate ──────────────────────────────


@router.post("/recalculate")
async def recalculate_all():
    """
    Força o recalculo do Health Score de todos os clientes Zenya ativos.
    Persiste novos registros em client_health.

    Retorna sumário com contagem por classificação.
    """
    try:
        results = await calculate_all_health_scores()
    except Exception as e:
        logger.error("[health/router] recalculate_all error: %s", e)
        raise HTTPException(status_code=500, detail=f"Recalculation failed: {e}")

    # Sumário por classificação
    summary: dict[str, int] = {"healthy": 0, "attention": 0, "risk": 0, "critical": 0}
    for r in results:
        cls = r.get("classification", "critical")
        summary[cls] = summary.get(cls, 0) + 1

    return {
        "status": "ok",
        "recalculated": len(results),
        "summary": summary,
        "scores": results,
    }


# ── GET /health/{client_id}/history ──────────────────────


@router.get("/{client_id}/history")
async def get_client_health_history(
    client_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Retorna o histórico de Health Score de um cliente, ordenado por data DESC.

    Parâmetros:
        limit: máximo de registros (1-100, default 20)
        offset: paginação (default 0)
    """
    history = await get_health_history(client_id, limit=limit, offset=offset)
    return {
        "client_id": client_id,
        "history": history,
        "count": len(history),
        "limit": limit,
        "offset": offset,
    }
