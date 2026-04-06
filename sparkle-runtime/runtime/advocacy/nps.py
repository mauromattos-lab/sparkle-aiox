"""
NPS Collection & Classification Engine — LIFECYCLE-2.4

Sends quarterly NPS surveys to eligible Zenya clients,
classifies responses, and triggers appropriate follow-up flows.

Eligibility rules (ALL must be true):
  - Client active > 30 days (zenya_clients.created_at)
  - No NPS collected in last 80 days (client_nps table)
  - Not in active churn intervention (health score < 60 OR active intervention task)
  - Onboarding complete (client_milestones contains zenya_active)

NPS Classification:
  9-10  (Promoter)  → thank you + referral proposal
  7-8   (Passive)   → improvement question
  0-6   (Detractor) → friday_alert task (NO commercial offers)

Global NPS = (% promoters) - (% detractors)

Public API:
  async collect_nps_eligible() -> dict
  async process_nps_response(client_id, score, feedback) -> dict
  async get_nps_global() -> dict
  async get_promoters() -> list[dict]
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase
from runtime.config import settings
from runtime.integrations import zapi

logger = logging.getLogger(__name__)


# ── Classification helpers ────────────────────────────────


def classify_nps(score: int) -> str:
    """Classify NPS score into promoter / passive / detractor."""
    if score >= 9:
        return "promoter"
    elif score >= 7:
        return "passive"
    else:
        return "detractor"


# ── Eligibility checks ────────────────────────────────────


async def _is_active_over_30_days(client: dict) -> bool:
    """Client must have been active for > 30 days."""
    created_at_str = client.get("created_at")
    if not created_at_str:
        return False
    created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    days_active = (datetime.now(timezone.utc) - created_dt).days
    return days_active > 30


async def _no_recent_nps(client_id: str) -> bool:
    """No NPS collected in the last 80 days."""
    eighty_days_ago = (datetime.now(timezone.utc) - timedelta(days=80)).isoformat()
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_nps")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .gte("collected_at", eighty_days_ago)
            .execute()
        )
        return (res.count or 0) == 0
    except Exception as e:
        logger.warning("[nps/eligibility] no_recent_nps check failed for %s: %s", client_id, e)
        return True  # fail open — do not block collection on DB error


async def _not_in_churn_intervention(client_id: str) -> bool:
    """
    Client should NOT be in active churn intervention.
    Checks: latest health score >= 60 AND no active intervention task in last 7 days.
    """
    try:
        # Check health score
        health_res = await asyncio.to_thread(
            lambda: supabase.table("client_health")
            .select("score")
            .eq("client_id", client_id)
            .order("calculated_at", desc=True)
            .limit(1)
            .execute()
        )
        if health_res.data:
            score = health_res.data[0].get("score", 100)
            if score < 60:
                return False

        # Check active intervention tasks in last 7 days
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        intervention_res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .in_("task_type", ["client_reactivation", "friday_alert"])
            .gte("created_at", seven_days_ago)
            .execute()
        )
        return (intervention_res.count or 0) == 0

    except Exception as e:
        logger.warning("[nps/eligibility] churn check failed for %s: %s", client_id, e)
        return True  # fail open


async def _onboarding_complete(client_id: str) -> bool:
    """Client must have zenya_active milestone."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_milestones")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("milestone_type", "zenya_active")
            .execute()
        )
        return (res.count or 0) > 0
    except Exception as e:
        logger.warning("[nps/eligibility] onboarding check failed for %s: %s", client_id, e)
        return False  # fail closed — onboarding must be confirmed


async def _is_eligible(client: dict) -> tuple[bool, str]:
    """
    Run all eligibility checks for a client.
    Returns (eligible: bool, reason: str).
    """
    client_id = client["id"]

    if not await _is_active_over_30_days(client):
        return False, "active_less_than_30_days"

    if not await _no_recent_nps(client_id):
        return False, "nps_collected_recently"

    if not await _not_in_churn_intervention(client_id):
        return False, "in_churn_intervention"

    if not await _onboarding_complete(client_id):
        return False, "onboarding_not_complete"

    return True, "eligible"


# ── NPS message sender ───────────────────────────────────


async def _send_nps_survey(client: dict) -> bool:
    """
    Send NPS survey message via Z-API to the client's WhatsApp.
    Uses business_name as zenya_name fallback.
    """
    phone = (
        (client.get("phone_number") or "")
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if not phone:
        logger.info("[nps/collect] client %s has no phone — skipping", client.get("business_name"))
        return False

    owner_name = client.get("business_name", "você")
    zenya_name = client.get("business_name", "nossa assistente")

    message = (
        f"Oi {owner_name}! 👋 De 0 a 10, o quanto você recomendaria a {zenya_name} "
        f"para um amigo empresário? Responda com o número e, se quiser, um comentário."
    )

    try:
        await asyncio.to_thread(lambda: zapi.send_text(phone, message))
        logger.info("[nps/collect] survey sent to %s (%s)", owner_name, phone)
        return True
    except Exception as e:
        logger.error("[nps/collect] failed to send survey to %s: %s", owner_name, e)
        return False


# ── Follow-up messages ───────────────────────────────────


async def _send_promoter_followup(client: dict) -> None:
    """9-10: Thank you + referral proposal."""
    phone = (
        (client.get("phone_number") or "")
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if not phone:
        return
    message = (
        "Que incrível, muito obrigado pela confiança! 🙌\n\n"
        "Que bom! Se indicar um amigo, ambos ganham 10% de desconto no próximo mês. "
        "Manda o contato e a gente cuida do resto!"
    )
    try:
        await asyncio.to_thread(lambda: zapi.send_text(phone, message))
    except Exception as e:
        logger.warning("[nps/followup] promoter message failed for %s: %s", client.get("business_name"), e)


async def _send_passive_followup(client: dict) -> None:
    """7-8: Ask what can be improved."""
    phone = (
        (client.get("phone_number") or "")
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if not phone:
        return
    message = "Obrigado! O que podemos melhorar para chegar a 10? Sua opinião é muito importante pra gente. 😊"
    try:
        await asyncio.to_thread(lambda: zapi.send_text(phone, message))
    except Exception as e:
        logger.warning("[nps/followup] passive message failed for %s: %s", client.get("business_name"), e)


async def _escalate_detractor_to_friday(
    client_id: str, client_name: str, score: int, feedback: Optional[str]
) -> None:
    """0-6: Create friday_alert task. NO commercial offers."""
    feedback_text = feedback or "(sem comentário)"
    try:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "friday_alert",
                "payload": {
                    "alert": "nps_detractor",
                    "client_id": client_id,
                    "client_name": client_name,
                    "nps_score": score,
                    "feedback": feedback_text,
                    "message": (
                        f"Cliente {client_name} deu NPS {score}. "
                        f"Feedback: {feedback_text}. Intervenção necessária."
                    ),
                },
                "status": "pending",
                "priority": 9,
            }).execute()
        )
        logger.info("[nps/detractor] friday_alert created for %s (score=%d)", client_name, score)
    except Exception as e:
        logger.error("[nps/detractor] failed to create friday_alert for %s: %s", client_name, e)


# ── Public API ────────────────────────────────────────────


async def collect_nps_eligible() -> dict:
    """
    Send NPS survey to all eligible clients.
    Called by quarterly cron (nps_quarterly).

    Returns:
        dict with total_checked, sent, skipped, errors and per-client details.
    """
    try:
        clients_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("id, business_name, phone_number, active, created_at")
            .eq("active", True)
            .execute()
        )
    except Exception as e:
        logger.error("[nps/collect] failed to fetch clients: %s", e)
        return {"total_checked": 0, "sent": 0, "skipped": 0, "errors": 1}

    clients = clients_res.data or []
    if not clients:
        logger.info("[nps/collect] no active clients found")
        return {"total_checked": 0, "sent": 0, "skipped": 0, "errors": 0}

    total_checked = len(clients)
    sent = 0
    skipped = 0
    errors = 0
    details = []

    for client in clients:
        client_id = client["id"]
        eligible, reason = await _is_eligible(client)

        if not eligible:
            skipped += 1
            details.append({
                "client_id": client_id,
                "name": client.get("business_name"),
                "status": "skipped",
                "reason": reason,
            })
            continue

        success = await _send_nps_survey(client)
        if success:
            # Record the survey send in client_nps with score=-1 (pending response)
            try:
                await asyncio.to_thread(
                    lambda cid=client_id: supabase.table("client_nps").insert({
                        "client_id": cid,
                        "score": -1,  # sentinel: survey sent but not yet answered
                        "feedback": None,
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    }).execute()
                )
            except Exception as e:
                logger.warning(
                    "[nps/collect] failed to insert pending record for %s: %s",
                    client_id, e,
                )

            sent += 1
            details.append({
                "client_id": client_id,
                "name": client.get("business_name"),
                "status": "sent",
            })
        else:
            errors += 1
            details.append({
                "client_id": client_id,
                "name": client.get("business_name"),
                "status": "error",
            })

    logger.info(
        "[nps/collect] done — total=%d sent=%d skipped=%d errors=%d",
        total_checked, sent, skipped, errors,
    )
    return {
        "total_checked": total_checked,
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }


async def process_nps_response(
    client_id: str, score: int, feedback: Optional[str] = None
) -> dict:
    """
    Process NPS response: persist, classify, and trigger appropriate follow-up flow.

    Args:
        client_id: UUID of the client (zenya_clients.id)
        score: NPS score 0-10
        feedback: optional text comment

    Returns:
        dict with classification and action taken.
    """
    if not (0 <= score <= 10):
        raise ValueError(f"NPS score must be 0-10, got {score}")

    classification = classify_nps(score)
    collected_at = datetime.now(timezone.utc).isoformat()

    # Upsert: update existing pending record (score=-1) if present, else insert
    try:
        pending_res = await asyncio.to_thread(
            lambda: supabase.table("client_nps")
            .select("id")
            .eq("client_id", client_id)
            .eq("score", -1)
            .order("collected_at", desc=True)
            .limit(1)
            .execute()
        )

        if pending_res.data:
            record_id = pending_res.data[0]["id"]
            await asyncio.to_thread(
                lambda: supabase.table("client_nps")
                .update({"score": score, "feedback": feedback, "collected_at": collected_at})
                .eq("id", record_id)
                .execute()
            )
        else:
            await asyncio.to_thread(
                lambda: supabase.table("client_nps").insert({
                    "client_id": client_id,
                    "score": score,
                    "feedback": feedback,
                    "collected_at": collected_at,
                }).execute()
            )
    except Exception as e:
        logger.error("[nps/process] failed to persist response for %s: %s", client_id, e)
        raise

    # Fetch client info for follow-up messages
    try:
        client_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("id, business_name, phone_number")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        client = (
            client_res.data
            if client_res is not None and hasattr(client_res, "data")
            else client_res
        )
    except Exception as e:
        logger.warning("[nps/process] failed to fetch client info for %s: %s", client_id, e)
        client = None

    client_name = client.get("business_name", "Cliente") if client else "Cliente"
    action = "none"

    if classification == "promoter":
        if client:
            await _send_promoter_followup(client)
        action = "promoter_followup_sent"

    elif classification == "passive":
        if client:
            await _send_passive_followup(client)
        action = "passive_followup_sent"

    else:  # detractor
        await _escalate_detractor_to_friday(client_id, client_name, score, feedback)
        action = "friday_alert_created"

    logger.info(
        "[nps/process] client=%s score=%d classification=%s action=%s",
        client_id, score, classification, action,
    )

    return {
        "client_id": client_id,
        "client_name": client_name,
        "score": score,
        "classification": classification,
        "action": action,
        "collected_at": collected_at,
    }


async def get_nps_global() -> dict:
    """
    Calculate global NPS score from all responses (excluding pending score=-1).

    Formula: NPS = (%promoters) - (%detractors)
    Range: -100 to +100

    Returns:
        dict with nps_score, total_responses, promoters, passives, detractors.
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_nps")
            .select("score")
            .gte("score", 0)  # exclude pending (-1)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.error("[nps/global] failed to fetch responses: %s", e)
        return {
            "nps_score": None,
            "total_responses": 0,
            "promoters": 0,
            "passives": 0,
            "detractors": 0,
            "error": str(e),
        }

    total = len(rows)
    if total == 0:
        return {
            "nps_score": None,
            "total_responses": 0,
            "promoters": 0,
            "passives": 0,
            "detractors": 0,
        }

    promoters = sum(1 for r in rows if r["score"] >= 9)
    detractors = sum(1 for r in rows if r["score"] <= 6)
    passives = total - promoters - detractors

    nps_score = round((promoters / total * 100) - (detractors / total * 100), 1)

    return {
        "nps_score": nps_score,
        "total_responses": total,
        "promoters": promoters,
        "passives": passives,
        "detractors": detractors,
        "promoter_pct": round(promoters / total * 100, 1),
        "detractor_pct": round(detractors / total * 100, 1),
    }


async def get_promoters() -> list[dict]:
    """
    List active promoters (score 9-10) with responses in the last 90 days.

    Returns:
        list of dicts with client_id, score, feedback, collected_at, client_name.
    """
    ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_nps")
            .select("client_id, score, feedback, collected_at")
            .gte("score", 9)
            .gte("collected_at", ninety_days_ago)
            .order("collected_at", desc=True)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.error("[nps/promoters] failed to fetch promoters: %s", e)
        return []

    if not rows:
        return []

    # Enrich with client names
    result = []
    for row in rows:
        cid = row["client_id"]
        try:
            client_res = await asyncio.to_thread(
                lambda c=cid: supabase.table("zenya_clients")
                .select("business_name")
                .eq("id", c)
                .maybe_single()
                .execute()
            )
            client_data = (
                client_res.data
                if client_res is not None and hasattr(client_res, "data")
                else client_res
            )
            row["client_name"] = client_data.get("business_name") if client_data else None
        except Exception:
            row["client_name"] = None
        result.append(row)

    return result
