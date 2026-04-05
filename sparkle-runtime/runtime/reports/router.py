"""
Reports router — /reports/* endpoints.

POST /reports/client/{client_id}      — generate and send report for one client
POST /reports/clients/all             — trigger bulk reports for all active clients
GET  /reports/client/{client_id}/preview — generate but do NOT send (preview only)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.handlers.client_report import (
    handle_client_report,
    handle_client_reports_bulk,
)

router = APIRouter(prefix="/reports", tags=["reports"])


# ── POST /reports/client/{client_id} ───────────────────────


@router.post("/client/{client_id}")
async def send_client_report(client_id: str):
    """
    Generate and send the monthly report for a single client via WhatsApp.
    Returns the report text and delivery status.
    """
    task = {
        "payload": {
            "client_id": client_id,
            "send": True,
        }
    }
    try:
        result = await handle_client_report(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ── POST /reports/clients/all ────────────────────────────────


@router.post("/clients/all")
async def send_all_client_reports():
    """
    Trigger bulk monthly reports for all active clients.
    Runs all reports in parallel and returns a summary.
    """
    task = {
        "payload": {
            "send": True,
        }
    }
    try:
        result = await handle_client_reports_bulk(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ── GET /reports/client/{client_id}/preview ─────────────────


@router.get("/client/{client_id}/preview")
async def preview_client_report(client_id: str):
    """
    Generate the monthly report for a client WITHOUT sending it.
    Useful for reviewing what will be sent before the cron fires.
    """
    task = {
        "payload": {
            "client_id": client_id,
            "send": False,
        }
    }
    try:
        result = await handle_client_report(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
