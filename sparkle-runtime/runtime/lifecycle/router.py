"""
Lifecycle router — /lifecycle/* endpoints (LIFECYCLE-3.2).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

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
