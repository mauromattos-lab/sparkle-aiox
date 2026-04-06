"""
LIFECYCLE-3.2 — First Real Message Detector.
Detects the first REAL message (not test/internal) for a client's Zenya.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)

INTERNAL_PHONES = {"5512981303249", "551299999999"}

TEST_PATTERNS = [
    re.compile(r"\bteste?\b", re.IGNORECASE),
    re.compile(r"\btesting\b", re.IGNORECASE),
    re.compile(r"\boi\s+[eE]\s+teste\b", re.IGNORECASE),
    re.compile(r"\btest\s+message\b", re.IGNORECASE),
    re.compile(r"^(oi|ola|hello|hi)$", re.IGNORECASE),
]


def is_test_message(content: str, sender_phone: str, owner_phone: str) -> bool:
    if not content:
        return True
    if sender_phone in INTERNAL_PHONES:
        return True
    if sender_phone == owner_phone:
        return True
    for pattern in TEST_PATTERNS:
        if pattern.search(content):
            return True
    return False


async def _has_first_message_milestone(client_uuid: str) -> bool:
    res = await asyncio.to_thread(
        lambda: supabase.table("client_milestones")
        .select("id", count="exact").eq("client_id", client_uuid)
        .eq("milestone_type", "first_real_message").execute()
    )
    return (res.count or 0) > 0


async def check_first_real_message(client_uuid: str) -> dict:
    if await _has_first_message_milestone(client_uuid):
        return {"status": "already_tracked", "client_id": client_uuid}

    client_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, client_id, business_name, phone_number, created_at")
        .eq("id", client_uuid).maybe_single().execute()
    )
    client = client_res.data if client_res and hasattr(client_res, "data") else client_res
    if not client:
        return {"status": "client_not_found"}

    owner_phone = client.get("phone_number", "")

    events_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_events")
        .select("id, event_type, payload, created_at")
        .eq("client_id", client_uuid)
        .order("created_at", desc=False).limit(100).execute()
    )
    events = events_res.data or []

    for event in events:
        payload = event.get("payload") or {}
        content = payload.get("message", "") or payload.get("text", "") or payload.get("content", "")
        sender = payload.get("sender", "") or payload.get("from", "") or payload.get("phone", "")

        if not is_test_message(content, sender, owner_phone):
            event_time = event.get("created_at", datetime.now(timezone.utc).isoformat())

            created_at = client.get("created_at", "")
            ttv_days = None
            if created_at:
                dt_start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                dt_event = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                ttv_days = max(1, (dt_event - dt_start).days)

            from runtime.onboarding.service import track_milestone
            await track_milestone(
                client.get("client_id", str(client_uuid)),
                "first_real_message",
                {"event_id": event.get("id"), "sender": sender, "ttv_days": ttv_days},
            )

            from runtime.lifecycle.congratulations import send_congratulations
            await send_congratulations(
                client_uuid=client_uuid,
                client_name=client.get("business_name", ""),
                phone=owner_phone,
                ttv_days=ttv_days,
            )

            return {
                "status": "first_real_message_detected", "client_id": client_uuid,
                "event_id": event.get("id"), "ttv_days": ttv_days,
            }

    return {"status": "no_real_messages_yet", "client_id": client_uuid, "events_checked": len(events)}


async def check_all_clients() -> dict:
    clients_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id").eq("active", True).execute()
    )
    clients = clients_res.data or []
    results = {"checked": 0, "detected": 0, "already_tracked": 0, "no_messages": 0}

    for c in clients:
        result = await check_first_real_message(c["id"])
        results["checked"] += 1
        s = result.get("status", "")
        if s == "first_real_message_detected":
            results["detected"] += 1
        elif s == "already_tracked":
            results["already_tracked"] += 1
        else:
            results["no_messages"] += 1

    logger.info("[first_message] check done: %s", results)
    return results
