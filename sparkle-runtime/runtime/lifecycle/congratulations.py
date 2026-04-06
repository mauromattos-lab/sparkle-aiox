"""
LIFECYCLE-3.2 — Congratulations Engine.
Sends congrats on first real message + notifies Mauro via Friday.
"""
from __future__ import annotations

import asyncio
import logging

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

MAURO_PHONE = "5512981303249"


async def send_congratulations(client_uuid, client_name, phone, ttv_days=None):
    results = {"client_message": False, "friday_alert": False}

    zenya_name = "Zenya"
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("display_slug").eq("id", client_uuid).maybe_single().execute()
        )
        data = res.data if res and hasattr(res, "data") else res
        if data and data.get("display_slug"):
            zenya_name = data["display_slug"]
    except Exception:
        pass

    ttv_text = f"Em {ttv_days} dias do contrato ao primeiro atendimento real. " if ttv_days else ""
    client_msg = (
        f"Parabens {client_name}!\n\n"
        f"Sua {zenya_name} acabou de atender o primeiro cliente real!\n"
        f"{ttv_text}Isso e incrivel!\n\n"
        f"Qualquer duvida, estamos aqui."
    )

    if phone:
        try:
            from runtime.integrations.zapi import send_text
            await asyncio.to_thread(send_text, phone, client_msg)
            results["client_message"] = True
            logger.info("[congrats] sent to %s (%s)", client_name, phone)
        except Exception as e:
            logger.error("[congrats] Z-API send failed for %s: %s", client_name, e)

    friday_msg = f"{client_name} teve primeiro atendimento real!"
    if ttv_days:
        friday_msg += f" TTV = {ttv_days} dias."

    try:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": getattr(settings, "sparkle_internal_client_id", None),
                "task_type": "friday_alert",
                "payload": {
                    "alert": "first_real_message",
                    "client_name": client_name,
                    "client_id": client_uuid,
                    "ttv_days": ttv_days,
                    "message": friday_msg,
                },
                "status": "pending", "priority": 8,
            }).execute()
        )
        results["friday_alert"] = True
    except Exception as e:
        logger.error("[congrats] friday alert failed: %s", e)

    return results
