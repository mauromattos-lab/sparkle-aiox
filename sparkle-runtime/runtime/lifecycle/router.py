"""
Lifecycle router — /lifecycle/* endpoints (LIFECYCLE-3.2, W2-CLC-2).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from runtime.lifecycle.first_message_detector import check_first_real_message, check_all_clients

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/check-first-messages")
async def force_check_all():
    try:
        result = await check_all_clients()
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check/{client_id}")
async def check_client(client_id: str):
    try:
        result = await check_first_real_message(client_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── W2-CLC-2: Weekly Client Report ──────────────────────────

@router.post("/report/weekly/{client_id}")
async def weekly_report_client(
    client_id: str,
    send: bool = Query(default=False, description="Se true, envia via WhatsApp; se false, dry-run"),
):
    """
    W2-CLC-2: Dispara relatório semanal para um cliente específico.
    ?send=false (default) retorna texto sem enviar (dry-run).
    ?send=true envia via Z-API.
    """
    try:
        from runtime.client_lifecycle.weekly_report import send_weekly_report
        result = await send_weekly_report(client_id, dry_run=not send)
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/weekly")
async def weekly_report_all(
    send: bool = Query(default=False, description="Se true, envia para todos; se false, dry-run"),
):
    """
    W2-CLC-2: Dispara relatório semanal para todos os clientes Zenya ativos.
    ?send=false (default) dry-run; ?send=true envia via WhatsApp.
    """
    try:
        from runtime.client_lifecycle.weekly_report import send_all_weekly_reports
        result = await send_all_weekly_reports(dry_run=not send)
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
