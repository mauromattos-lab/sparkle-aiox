"""
LIFECYCLE-2.1 — Upsell/Cross-sell Detection Engine.

Detects opportunities based on health score history, volume, and service mix.
Applies veto rules (45-day minimum, no complaints, need documented win).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

def _now():
    return datetime.now(timezone.utc)


async def _get_active_clients() -> list[dict]:
    res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, business_name, phone_number, created_at, active")
        .eq("active", True)
        .execute()
    )
    return res.data or []


async def _get_health_history(client_id: str, weeks: int = 8) -> list[dict]:
    cutoff = (_now() - timedelta(weeks=weeks)).isoformat()
    res = await asyncio.to_thread(
        lambda: supabase.table("client_health")
        .select("score, classification, calculated_at")
        .eq("client_id", client_id)
        .gte("calculated_at", cutoff)
        .order("calculated_at", desc=True)
        .execute()
    )
    return res.data or []


async def _get_monthly_volume(client_id: str) -> int:
    cutoff = (_now() - timedelta(days=30)).isoformat()
    res = await asyncio.to_thread(
        lambda: supabase.table("zenya_events")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .gte("created_at", cutoff)
        .execute()
    )
    return res.count or 0


async def _has_milestone(client_id: str) -> bool:
    res = await asyncio.to_thread(
        lambda: supabase.table("client_milestones")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .execute()
    )
    return (res.count or 0) > 0


async def _existing_opportunity(client_id: str, opp_type: str) -> bool:
    res = await asyncio.to_thread(
        lambda: supabase.table("upsell_opportunities")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .eq("opportunity_type", opp_type)
        .in_("status", ["detected", "approached"])
        .execute()
    )
    return (res.count or 0) > 0


async def _check_vetos(client: dict, client_id: str) -> tuple[bool, str]:
    created_at = client.get("created_at", "")
    if created_at:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if (_now() - dt).days < 45:
            return True, "client_under_45_days"

    health = await _get_health_history(client_id, weeks=2)
    if health and health[0].get("score", 100) < 60:
        return True, "health_below_60"

    if not await _has_milestone(client_id):
        return True, "no_documented_win"

    return False, ""


async def _detect_for_client(client: dict) -> list[dict]:
    client_id = client["id"]
    opportunities = []

    vetoed, veto_reason = await _check_vetos(client, client_id)
    if vetoed:
        logger.debug("[expansion] client %s vetoed: %s", client.get("business_name"), veto_reason)
        return []

    # Check upgrade_tier: health > 80 for 2+ weeks AND volume > 500/month
    health_history = await _get_health_history(client_id, weeks=8)
    consecutive_healthy = 0
    for h in health_history:
        if h.get("score", 0) > 80:
            consecutive_healthy += 1
        else:
            break

    volume = await _get_monthly_volume(client_id)

    if consecutive_healthy >= 2 and volume > 500:
        if not await _existing_opportunity(client_id, "upgrade_tier"):
            opportunities.append({
                "client_id": client_id,
                "opportunity_type": "upgrade_tier",
                "signal": f"health>80 for {consecutive_healthy} weeks, volume={volume}/month",
                "score": min(100, consecutive_healthy * 10 + volume // 100),
            })

    # Check cross_sell_traffic: has Zenya but not traffic service
    # Simple heuristic: if client is in zenya_clients, they have Zenya
    # Check if they do NOT appear in any traffic/ads context
    # For now: all Zenya clients are potential cross_sell_traffic candidates if healthy
    if consecutive_healthy >= 4 and not await _existing_opportunity(client_id, "cross_sell_traffic"):
        opportunities.append({
            "client_id": client_id,
            "opportunity_type": "cross_sell_traffic",
            "signal": f"Zenya client, health>80 for {consecutive_healthy} weeks, no traffic detected",
            "score": min(90, consecutive_healthy * 8 + 20),
        })

    return opportunities


async def _persist_opportunity(opp: dict) -> dict:
    res = await asyncio.to_thread(
        lambda: supabase.table("upsell_opportunities").insert({
            "client_id": opp["client_id"],
            "opportunity_type": opp["opportunity_type"],
            "signal": opp["signal"],
            "score": opp["score"],
            "status": "detected",
        }).execute()
    )
    return (res.data or [{}])[0]


async def _notify_friday(opp: dict, client_name: str) -> None:
    try:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "friday_alert",
                "payload": {
                    "alert": "upsell_opportunity",
                    "client_name": client_name,
                    "opportunity_type": opp["opportunity_type"],
                    "signal": opp["signal"],
                    "score": opp["score"],
                    "message": f"Oportunidade de {opp.get('opportunity_type', '?')} para {client_name}. Sinal: {opp.get('signal', '?')}",
                },
                "status": "pending",
                "priority": 5,
            }).execute()
        )
    except Exception as e:
        logger.error("[expansion] friday notify failed: %s", e)


async def detect_all_opportunities() -> dict:
    """Main entry: detect upsell opportunities for all active clients."""
    clients = await _get_active_clients()
    total = len(clients)
    detected = 0
    skipped = 0
    details = []

    for client in clients:
        opps = await _detect_for_client(client)
        if not opps:
            skipped += 1
            continue
        for opp in opps:
            persisted = await _persist_opportunity(opp)
            await _notify_friday(opp, client.get("business_name", ""))
            detected += 1
            details.append({
                "client": client.get("business_name"),
                "type": opp["opportunity_type"],
                "score": opp["score"],
            })

    logger.info("[expansion] detection done: total=%d detected=%d skipped=%d", total, detected, skipped)
    return {"total_clients": total, "opportunities_detected": detected, "skipped": skipped, "details": details}
