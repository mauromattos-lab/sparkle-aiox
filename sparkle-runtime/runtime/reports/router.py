"""
Reports router — /reports/* endpoints.

POST /reports/client/{client_id}          — generate and send report for one client
POST /reports/client/{client_id}?send=false — preview/dry-run without sending
POST /reports/clients/all                 — trigger bulk reports for all active clients
POST /reports/clients/all?send=false      — bulk dry-run preview
GET  /reports/client/{client_id}/preview  — alias for preview (send=false)

AC-7: endpoint supports ?send=false for dry-run / preview.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from runtime.tasks.handlers.client_report import (
    handle_client_report,
    handle_client_reports_bulk,
)

router = APIRouter(prefix="/reports", tags=["reports"])


# ── POST /reports/client/{client_id} ───────────────────────


@router.post("/client/{client_id}")
async def send_client_report(
    client_id: str,
    send: bool = Query(default=True, description="Set false for preview only (no WhatsApp send)"),
):
    """
    Generate the monthly report for a single client.

    - send=true (default): generates and sends via WhatsApp
    - send=false: generates and returns text only — no message sent
    Returns the report text and delivery status.
    """
    task = {
        "payload": {
            "client_id": client_id,
            "send": send,
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
async def send_all_client_reports(
    send: bool = Query(default=True, description="Set false for bulk dry-run preview"),
):
    """
    Trigger monthly reports for all active clients.

    - send=true (default): generates and sends via WhatsApp for each client
    - send=false: dry-run — generates all reports, returns texts, sends nothing
    Returns a summary with per-client results including report_text for audit.
    """
    task = {
        "payload": {
            "send": send,
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
    Useful for reviewing the text before the scheduled cron fires.
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
