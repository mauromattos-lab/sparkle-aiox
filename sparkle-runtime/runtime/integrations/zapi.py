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


def _is_phone_allowed(phone: str) -> bool:
    """
    SAFEGUARD: Only allow sends to explicitly whitelisted numbers.
    Prevents accidental messages to clients during testing/validation.
    Whitelist loaded from ZAPI_ALLOWED_PHONES env var (comma-separated)
    plus Mauro's number (always allowed).
    """
    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    allowed = {settings.mauro_whatsapp}
    extra = getattr(settings, "zapi_allowed_phones", "")
    if extra:
        allowed.update(p.strip() for p in extra.split(",") if p.strip())
    return clean in allowed


def send_text(phone: str, message: str) -> dict:
    """
    Send a text message to a WhatsApp number.
    phone format: "5511999999999" (country code + number, no +)
    SAFEGUARD: blocked if phone not in whitelist.
    """
    if not _is_phone_allowed(phone):
        import logging
        logging.getLogger("zapi").warning(
            "[BLOCKED] send_text to %s — not in whitelist. Message: %.60s...",
            phone, message,
        )
        return {"blocked": True, "reason": "phone not in ZAPI_ALLOWED_PHONES"}
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
    SAFEGUARD: blocked if phone not in whitelist.
    """
    if not _is_phone_allowed(phone):
        import logging
        logging.getLogger("zapi").warning(
            "[BLOCKED] send_audio to %s — not in whitelist", phone,
        )
        return {"blocked": True, "reason": "phone not in ZAPI_ALLOWED_PHONES"}
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
