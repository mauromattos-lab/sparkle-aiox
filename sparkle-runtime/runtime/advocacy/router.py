"""
Advocacy router — /advocacy/* endpoints.

GET  /advocacy/nps/{client_id}   — NPS history for client
POST /advocacy/nps/collect       — trigger NPS collection for eligible clients
POST /advocacy/nps/response      — record NPS response
GET  /advocacy/promoters         — list promoters (score 9-10, last 90 days)
GET  /advocacy/nps/global        — global NPS score
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runtime.advocacy.nps import (
    collect_nps_eligible,
    process_nps_response,
    get_nps_global,
    get_promoters,
)
from runtime.db import supabase

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request models ────────────────────────────────────────


class NpsResponseBody(BaseModel):
    client_id: str = Field(..., description="UUID of the client (zenya_clients.id)")
    score: int = Field(..., ge=0, le=10, description="NPS score 0-10")
    feedback: Optional[str] = Field(None, description="Optional text comment from client")


# ── GET /advocacy/nps/global ──────────────────────────────
# Must be registered BEFORE /{client_id} to avoid path ambiguity


@router.get("/nps/global")
async def nps_global():
    """
    Returns the global NPS score calculated from all collected responses.
    Formula: NPS = (% promoters) - (% detractors). Range: -100 to +100.
    """
    try:
        result = await get_nps_global()
        return result
    except Exception as e:
        logger.error("[advocacy/router] nps_global error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to calculate global NPS: {e}")


# ── GET /advocacy/promoters ───────────────────────────────


@router.get("/promoters")
async def list_promoters():
    """
    List active promoters (score 9-10) who responded in the last 90 days.
    Includes client_name enriched from zenya_clients.
    """
    try:
        result = await get_promoters()
        return {"promoters": result, "count": len(result)}
    except Exception as e:
        logger.error("[advocacy/router] list_promoters error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch promoters: {e}")


# ── GET /advocacy/nps/{client_id} ─────────────────────────


@router.get("/nps/{client_id}")
async def get_client_nps_history(client_id: str):
    """
    Returns full NPS history for a specific client, ordered by collected_at DESC.
    Excludes pending records (score=-1).
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_nps")
            .select("id, score, feedback, collected_at")
            .eq("client_id", client_id)
            .gte("score", 0)  # exclude pending (-1)
            .order("collected_at", desc=True)
            .execute()
        )
        rows = res.data or []
        return {
            "client_id": client_id,
            "history": rows,
            "count": len(rows),
        }
    except Exception as e:
        logger.error("[advocacy/router] get_client_nps_history error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch NPS history: {e}")


# ── POST /advocacy/nps/collect ────────────────────────────


@router.post("/nps/collect")
async def trigger_nps_collection():
    """
    Trigger NPS survey collection for all eligible clients.
    Eligibility: active > 30 days, no NPS in last 80 days,
    not in churn intervention, onboarding complete.
    """
    try:
        result = await collect_nps_eligible()
        return {"status": "ok", **result}
    except Exception as e:
        logger.error("[advocacy/router] trigger_nps_collection error: %s", e)
        raise HTTPException(status_code=500, detail=f"NPS collection failed: {e}")


# ── POST /advocacy/nps/response ───────────────────────────


@router.post("/nps/response")
async def record_nps_response(body: NpsResponseBody):
    """
    Record an NPS response from a client.
    Persists the score, classifies (promoter/passive/detractor),
    and triggers the appropriate follow-up flow.

    - 9-10 (Promoter): sends thank you + referral proposal via WhatsApp
    - 7-8  (Passive): asks what can be improved
    - 0-6  (Detractor): creates friday_alert task (NO commercial messages)
    """
    try:
        result = await process_nps_response(
            client_id=body.client_id,
            score=body.score,
            feedback=body.feedback,
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("[advocacy/router] record_nps_response error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to process NPS response: {e}")
