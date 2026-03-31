"""
Z-API integration — send messages back to WhatsApp.

All outbound WhatsApp communication goes through this module.
Credentials come from settings (never hardcoded).
"""
from __future__ import annotations

from typing import Optional

import httpx

from runtime.config import settings


def _base_url() -> str:
    base = settings.zapi_base_url.rstrip("/")
    # If base_url already contains the full instance path, use it directly
    if "/instances/" in base:
        return base
    return f"{base}/instances/{settings.zapi_instance_id}/token/{settings.zapi_token}"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "client-token": settings.zapi_client_token,
    }


def send_text(phone: str, message: str) -> dict:
    """
    Send a text message to a WhatsApp number.
    phone format: "5511999999999" (country code + number, no +)
    """
    url = f"{_base_url()}/send-text"
    payload = {"phone": phone, "message": message}

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def send_audio(phone: str, audio_url: str) -> dict:
    """
    Send an audio message by URL. The URL must be publicly accessible.
    Z-API downloads the audio and sends it as voice message.
    """
    url = f"{_base_url()}/send-audio"
    payload = {"phone": phone, "audio": audio_url}

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def send_reaction(phone: str, message_id: str, reaction: str = "✅") -> dict:
    """React to a message — useful to acknowledge Friday received the audio."""
    url = f"{_base_url()}/send-reaction"
    payload = {"phone": phone, "messageId": message_id, "reaction": reaction}

    with httpx.Client(timeout=10) as client:
        resp = client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def get_status() -> bool:
    """Check if Z-API instance is connected. Used by /health."""
    try:
        url = f"{_base_url()}/status"
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, headers=_headers())
            data = resp.json()
            return data.get("connected", False)
    except Exception:
        return False
