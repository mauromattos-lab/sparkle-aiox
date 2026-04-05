"""
Asaas billing integration — async HTTP client using httpx.

Handles customer creation, subscription management, and payment listing.
Base URL switches between sandbox and production via settings.asaas_sandbox.
Auth: access_token header (Bearer token).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from runtime.config import settings

logger = logging.getLogger(__name__)

_SANDBOX_URL = "https://api-sandbox.asaas.com/v3"
_PRODUCTION_URL = "https://api.asaas.com/v3"


def _base_url() -> str:
    return _SANDBOX_URL if settings.asaas_sandbox else _PRODUCTION_URL


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "access_token": settings.asaas_api_key,
    }


async def create_customer(
    name: str,
    cpf_cnpj: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> str:
    """
    Create a customer in Asaas.
    Returns the asaas_customer_id (e.g. "cus_xxx").
    """
    payload: dict = {"name": name, "cpfCnpj": cpf_cnpj}
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_base_url()}/customers",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    customer_id: str = data["id"]
    logger.info("[asaas] customer created: %s (%s)", customer_id, name)
    return customer_id


async def create_subscription(
    customer_id: str,
    value: float,
    billing_type: str = "PIX",
    description: str = "",
    next_due_date: Optional[str] = None,
) -> str:
    """
    Create a monthly subscription in Asaas.
    next_due_date: ISO date string "YYYY-MM-DD". Defaults to tomorrow.
    Returns the asaas_subscription_id (e.g. "sub_xxx").
    """
    if next_due_date is None:
        next_due_date = (date.today() + timedelta(days=1)).isoformat()

    payload = {
        "customer": customer_id,
        "billingType": billing_type,
        "value": value,
        "cycle": "MONTHLY",
        "nextDueDate": next_due_date,
        "description": description,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_base_url()}/subscriptions",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    subscription_id: str = data["id"]
    logger.info("[asaas] subscription created: %s for customer %s", subscription_id, customer_id)
    return subscription_id


async def get_subscription(subscription_id: str) -> dict:
    """
    Fetch subscription details from Asaas.
    Returns the full subscription object.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_base_url()}/subscriptions/{subscription_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def list_payments(subscription_id: Optional[str] = None) -> list[dict]:
    """
    List payments. Optionally filtered by subscription_id.
    Returns list of payment objects.
    """
    params: dict = {}
    if subscription_id:
        params["subscription"] = subscription_id

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_base_url()}/payments",
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    return data.get("data", [])
