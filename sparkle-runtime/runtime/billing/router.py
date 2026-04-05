"""
Billing router — Asaas integration endpoints.

POST /billing/webhook/asaas           — receives Asaas webhook events
POST /billing/subscribe/{client_id}   — creates customer + subscription for a client
GET  /billing/subscriptions           — list all subscriptions with status
GET  /billing/client/{client_id}      — get subscription + payments for a client
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from runtime.config import settings
from runtime.db import supabase
from runtime.integrations import asaas as asaas_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ── POST /billing/webhook/asaas ──────────────────────────────


@router.post("/webhook/asaas")
async def asaas_webhook(request: Request):
    """
    Receives Asaas webhook events and updates the payments table accordingly.

    Handled events:
    - PAYMENT_RECEIVED: marks payment as RECEIVED, records paid_date
    - PAYMENT_OVERDUE: marks payment as OVERDUE, triggers billing_alert task
    - PAYMENT_CREATED: upserts payment record
    - PAYMENT_DELETED: marks payment as DELETED
    """
    # Validate Asaas webhook token (fail-closed)
    expected_token = settings.asaas_webhook_token
    if not expected_token:
        logger.error("[billing/webhook] ASAAS_WEBHOOK_TOKEN not configured — rejecting request")
        return JSONResponse(status_code=401, content={"detail": "Webhook token not configured"})

    provided_token = request.headers.get("asaas-access-token", "")
    if provided_token != expected_token:
        logger.warning("[billing/webhook] invalid asaas-access-token from %s", request.client.host if request.client else "unknown")
        return JSONResponse(status_code=401, content={"detail": "Invalid webhook token"})

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event = body.get("event", "")
    payment_data = body.get("payment", {})
    asaas_payment_id = payment_data.get("id")

    logger.info("[billing/webhook] event=%s payment=%s", event, asaas_payment_id)

    if not asaas_payment_id:
        return {"status": "ignored", "reason": "no payment id"}

    if event == "PAYMENT_CREATED":
        await _upsert_payment(payment_data)

    elif event == "PAYMENT_RECEIVED":
        paid_date = payment_data.get("paymentDate") or payment_data.get("clientPaymentDate")
        await asyncio.to_thread(
            lambda: supabase.table("payments")
            .update({
                "status": "RECEIVED",
                "paid_date": paid_date,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("asaas_payment_id", asaas_payment_id)
            .execute()
        )
        logger.info("[billing/webhook] payment RECEIVED: %s", asaas_payment_id)

    elif event == "PAYMENT_OVERDUE":
        await asyncio.to_thread(
            lambda: supabase.table("payments")
            .update({
                "status": "OVERDUE",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("asaas_payment_id", asaas_payment_id)
            .execute()
        )
        logger.warning("[billing/webhook] payment OVERDUE: %s", asaas_payment_id)
        # Trigger billing_alert task for Friday to notify Mauro
        await _trigger_billing_alert(asaas_payment_id, payment_data)

    elif event == "PAYMENT_DELETED":
        await asyncio.to_thread(
            lambda: supabase.table("payments")
            .update({
                "status": "DELETED",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("asaas_payment_id", asaas_payment_id)
            .execute()
        )
        logger.info("[billing/webhook] payment DELETED: %s", asaas_payment_id)

    return {"status": "ok", "event": event}


async def _upsert_payment(payment_data: dict) -> None:
    """Upsert a payment record from Asaas payload, linked to its subscription."""
    asaas_payment_id = payment_data.get("id")
    asaas_subscription_id = payment_data.get("subscription")

    # Look up our internal subscription_id
    subscription_id = None
    if asaas_subscription_id:
        res = await asyncio.to_thread(
            lambda: supabase.table("subscriptions")
            .select("id")
            .eq("asaas_subscription_id", asaas_subscription_id)
            .maybe_single()
            .execute()
        )
        if res.data:
            subscription_id = res.data["id"]

    row = {
        "asaas_payment_id": asaas_payment_id,
        "amount": payment_data.get("value"),
        "due_date": payment_data.get("dueDate"),
        "status": payment_data.get("status", "PENDING"),
        "billing_type": payment_data.get("billingType"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if subscription_id:
        row["subscription_id"] = subscription_id

    await asyncio.to_thread(
        lambda: supabase.table("payments")
        .upsert(row, on_conflict="asaas_payment_id")
        .execute()
    )


async def _trigger_billing_alert(asaas_payment_id: str, payment_data: dict) -> None:
    """Create a billing_alert task so Friday notifies Mauro about overdue payment."""
    try:
        task_row = {
            "task_type": "billing_alert",
            "agent_id": "friday",
            "status": "pending",
            "payload": {
                "asaas_payment_id": asaas_payment_id,
                "value": payment_data.get("value"),
                "due_date": payment_data.get("dueDate"),
                "customer": payment_data.get("customer"),
                "description": payment_data.get("description", ""),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert(task_row).execute()
        )
        logger.info("[billing/webhook] billing_alert task enqueued for %s", asaas_payment_id)

        # Execute inline (same pattern as scheduler._run_and_execute)
        if res.data:
            try:
                from runtime.tasks.worker import execute_task
                task = res.data[0]
                await execute_task(task)
                logger.info("[billing/webhook] billing_alert task executed inline for %s", asaas_payment_id)
            except Exception as exec_err:
                # Task remains as 'pending' in Supabase for retry via poll
                logger.warning("[billing/webhook] billing_alert inline execution failed (will retry via poll): %s", exec_err)
    except Exception as e:
        logger.error("[billing/webhook] failed to enqueue billing_alert: %s", e)


# ── POST /billing/subscribe/{client_id} ─────────────────────


@router.post("/subscribe/{client_id}")
async def subscribe_client(client_id: str, billing_type: str = "PIX"):
    """
    Create an Asaas customer + monthly subscription for a client.
    Reads client data (name, cpf_cnpj, email, phone, mrr) from the clients table.
    """
    # Fetch client from DB
    res = await asyncio.to_thread(
        lambda: supabase.table("clients")
        .select("id, name, cpf_cnpj, email, phone, mrr")
        .eq("id", client_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    client = res.data
    name = client.get("name") or ""
    cpf_cnpj = client.get("cpf_cnpj") or ""
    email = client.get("email")
    phone = client.get("phone")
    mrr = float(client.get("mrr") or 0)

    if not cpf_cnpj:
        raise HTTPException(status_code=422, detail="Client has no cpf_cnpj — required for Asaas")
    if mrr <= 0:
        raise HTTPException(status_code=422, detail="Client MRR is zero or missing")

    # Check if subscription already exists
    existing = await asyncio.to_thread(
        lambda: supabase.table("subscriptions")
        .select("id, asaas_subscription_id, status")
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )
    if existing.data:
        return {
            "status": "already_exists",
            "subscription": existing.data,
        }

    # Create Asaas customer
    try:
        asaas_customer_id = await asaas_client.create_customer(
            name=name,
            cpf_cnpj=cpf_cnpj,
            email=email,
            phone=phone,
        )
    except Exception as e:
        logger.error("[billing/subscribe] create_customer failed for %s: %s", client_id, e)
        raise HTTPException(status_code=502, detail=f"Asaas create_customer failed: {e}")

    # Create Asaas subscription
    try:
        asaas_subscription_id = await asaas_client.create_subscription(
            customer_id=asaas_customer_id,
            value=mrr,
            billing_type=billing_type,
            description=f"Sparkle AIOX — {name}",
        )
    except Exception as e:
        logger.error("[billing/subscribe] create_subscription failed for %s: %s", client_id, e)
        raise HTTPException(status_code=502, detail=f"Asaas create_subscription failed: {e}")

    # Persist to subscriptions table
    now = datetime.now(timezone.utc).isoformat()
    sub_row = {
        "client_id": client_id,
        "asaas_customer_id": asaas_customer_id,
        "asaas_subscription_id": asaas_subscription_id,
        "billing_type": billing_type,
        "monthly_value": mrr,
        "cycle": "MONTHLY",
        "status": "ACTIVE",
        "created_at": now,
        "updated_at": now,
    }
    res2 = await asyncio.to_thread(
        lambda: supabase.table("subscriptions").insert(sub_row).execute()
    )
    inserted = res2.data[0] if res2.data else sub_row

    logger.info(
        "[billing/subscribe] client=%s asaas_customer=%s sub=%s value=%.2f",
        client_id, asaas_customer_id, asaas_subscription_id, mrr,
    )
    return {
        "status": "created",
        "subscription": inserted,
    }


# ── GET /billing/subscriptions ───────────────────────────────


@router.get("/subscriptions")
async def list_subscriptions():
    """List all subscriptions with client name and status."""
    res = await asyncio.to_thread(
        lambda: supabase.table("subscriptions")
        .select("*, clients(name, email)")
        .order("created_at", desc=True)
        .execute()
    )
    return {"subscriptions": res.data or []}


# ── GET /billing/client/{client_id} ─────────────────────────


@router.get("/client/{client_id}")
async def get_client_billing(client_id: str):
    """
    Return subscription details + all payments for a given client.
    """
    sub_res = await asyncio.to_thread(
        lambda: supabase.table("subscriptions")
        .select("*")
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )
    subscription = sub_res.data

    payments: list[dict] = []
    if subscription:
        pay_res = await asyncio.to_thread(
            lambda: supabase.table("payments")
            .select("*")
            .eq("subscription_id", subscription["id"])
            .order("due_date", desc=True)
            .execute()
        )
        payments = pay_res.data or []

    return {
        "client_id": client_id,
        "subscription": subscription,
        "payments": payments,
    }
