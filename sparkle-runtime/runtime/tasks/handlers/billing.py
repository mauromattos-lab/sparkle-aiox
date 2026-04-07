"""
Billing task handlers.

handle_create_subscription — creates Asaas customer + subscription for a client.
handle_billing_alert       — sends WhatsApp alert to Mauro about overdue payment.
"""
from __future__ import annotations

import asyncio
import logging

from runtime.config import settings
from runtime.db import supabase
from runtime.integrations import asaas as asaas_client

logger = logging.getLogger(__name__)


async def handle_create_subscription(task: dict) -> dict:
    """
    Task payload expected:
    {
        "client_id": "uuid",
        "billing_type": "PIX"  # optional, defaults to PIX
    }

    Creates Asaas customer + subscription and persists to subscriptions table.
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id")
    billing_type = payload.get("billing_type", "PIX")

    if not client_id:
        return {"error": "client_id is required in payload"}

    # Delegate to the billing router logic via a direct import to avoid duplication
    from runtime.billing.router import subscribe_client
    try:
        result = await subscribe_client(client_id=client_id, billing_type=billing_type)
        return result
    except Exception as e:
        logger.error("[handle_create_subscription] failed for client %s: %s", client_id, e)
        return {"error": str(e)}


async def handle_billing_alert(task: dict) -> dict:
    """
    Task payload expected:
    {
        "asaas_payment_id": "pay_xxx",
        "value": 500.00,
        "due_date": "2026-04-10",
        "customer": "cus_xxx",
        "description": "Sparkle AIOX — Cliente X"
    }

    Sends a WhatsApp message to Mauro (MAURO_WHATSAPP) about the overdue payment.
    Also tries to resolve the client name from subscriptions table.
    """
    payload = task.get("payload", {})
    asaas_payment_id = payload.get("asaas_payment_id", "?")
    value = payload.get("value", 0)
    due_date = payload.get("due_date", "?")
    description = payload.get("description", "")
    asaas_customer_id = payload.get("customer", "")

    # Try to find client name via subscriptions table
    client_name = description
    if asaas_customer_id:
        try:
            res = await asyncio.to_thread(
                lambda: supabase.table("subscriptions")
                .select("monthly_value, clients(name)")
                .eq("asaas_customer_id", asaas_customer_id)
                .maybe_single()
                .execute()
            )
            if res.data and res.data.get("clients"):
                client_name = res.data["clients"].get("name", description)
        except Exception as e:
            logger.warning("[handle_billing_alert] could not fetch client name: %s", e)

    msg = (
        f"⚠️ *Cobrança em atraso — Sparkle AIOX*\n\n"
        f"Cliente: *{client_name}*\n"
        f"Valor: R$ {value:.2f}\n"
        f"Vencimento: {due_date}\n"
        f"ID Asaas: `{asaas_payment_id}`\n\n"
        f"Verifique no painel Asaas ou contate o cliente."
    )

    if not settings.mauro_whatsapp:
        logger.warning("[handle_billing_alert] MAURO_WHATSAPP not configured — alert not sent")
        return {"status": "skipped", "reason": "MAURO_WHATSAPP not configured", "message": msg}

    try:
        from runtime.integrations.zapi import send_text
        send_text(settings.mauro_whatsapp, msg)
        logger.info("[handle_billing_alert] overdue alert sent to %s", settings.mauro_whatsapp)
        return {"status": "sent", "to": settings.mauro_whatsapp, "payment_id": asaas_payment_id}
    except Exception as e:
        logger.error("[handle_billing_alert] failed to send WhatsApp alert: %s", e)
        return {"error": str(e), "message": msg}
