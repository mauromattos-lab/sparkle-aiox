"""
LIFECYCLE-2.3 - Conversion Tracking Engine.

Tracks the full proposal -> response -> contract funnel for leads.
All timestamps are stored on the leads table; no separate table needed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


async def _get_lead(lead_id: str) -> dict | None:
    """Fetch a single lead by UUID."""
    result = await asyncio.to_thread(
        lambda: supabase.table("leads")
        .select("*")
        .eq("id", lead_id)
        .single()
        .execute()
    )
    return result.data or None


async def _update_lead(lead_id: str, patch: dict) -> dict:
    """Patch lead fields and return updated row."""
    patch["updated_at"] = _now().isoformat()
    result = await asyncio.to_thread(
        lambda: supabase.table("leads")
        .update(patch)
        .eq("id", lead_id)
        .execute()
    )
    rows = result.data or []
    if not rows:
        raise ValueError(f"Lead {lead_id!r} not found or update failed")
    return rows[0]


async def record_proposal_sent(lead_id: str) -> dict:
    """
    Record when a proposal was sent to a lead.
    Sets proposal_sent=true and proposal_sent_at=now() if not already set.
    Increments touchpoints_count.
    """
    lead = await _get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id!r} not found")

    patch: dict = {
        "proposal_sent": True,
    }

    # Only set sent_at and increment touchpoints once (BUG-5 fix: idempotent)
    if not lead.get("proposal_sent_at"):
        patch["proposal_sent_at"] = _now().isoformat()
        patch["touchpoints_count"] = (lead.get("touchpoints_count") or 0) + 1

    # Advance status to proposta_enviada unless already further in the funnel
    current_status = lead.get("status", "")
    if current_status not in ("proposta_enviada", "respondeu", "cliente", "perdido", "fechado"):
        patch["status"] = "proposta_enviada"

    updated = await _update_lead(lead_id, patch)
    logger.info("[conversion] proposal_sent recorded -- lead=%s", lead_id)
    return {
        "lead_id": lead_id,
        "event": "proposal_sent",
        "proposal_sent_at": updated.get("proposal_sent_at"),
        "status": updated.get("status"),
        "touchpoints_count": updated.get("touchpoints_count"),
    }


async def record_first_response(lead_id: str) -> dict:
    """
    Record the first response after a proposal was sent.
    Sets first_response_at=now() if not already set.
    Advances status to negotiation.
    """
    lead = await _get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id!r} not found")

    patch: dict = {
        "touchpoints_count": (lead.get("touchpoints_count") or 0) + 1,
    }

    if not lead.get("first_response_at"):
        patch["first_response_at"] = _now().isoformat()

    current_status = lead.get("status", "")
    if current_status not in ("respondeu", "cliente", "perdido", "fechado"):
        patch["status"] = "respondeu"

    updated = await _update_lead(lead_id, patch)
    logger.info("[conversion] first_response recorded -- lead=%s", lead_id)
    return {
        "lead_id": lead_id,
        "event": "first_response",
        "first_response_at": updated.get("first_response_at"),
        "status": updated.get("status"),
        "touchpoints_count": updated.get("touchpoints_count"),
    }


async def record_contract_signed(lead_id: str) -> dict:
    """
    Record contract signature.
    Sets contract_signed_at, status=converted, closed_at=now().
    Calculates time_to_convert (proposal_sent_at -> contract_signed_at).
    """
    lead = await _get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id!r} not found")

    now_ts = _now()
    patch: dict = {
        "contract_signed_at": now_ts.isoformat(),
        "status": "cliente",
        "closed_at": now_ts.isoformat(),
        "touchpoints_count": (lead.get("touchpoints_count") or 0) + 1,
    }

    time_to_convert_days: float | None = None
    if lead.get("proposal_sent_at"):
        try:
            sent_at = datetime.fromisoformat(lead["proposal_sent_at"].replace("Z", "+00:00"))
            delta = now_ts - sent_at
            time_to_convert_days = round(delta.total_seconds() / 86400, 2)
        except Exception as e:
            logger.warning("[conversion] could not compute time_to_convert: %s", e)

    updated = await _update_lead(lead_id, patch)
    logger.info(
        "[conversion] contract_signed recorded -- lead=%s time_to_convert=%.1fd",
        lead_id, time_to_convert_days or 0,
    )
    return {
        "lead_id": lead_id,
        "event": "contract_signed",
        "contract_signed_at": updated.get("contract_signed_at"),
        "status": updated.get("status"),
        "time_to_convert_days": time_to_convert_days,
        "touchpoints_count": updated.get("touchpoints_count"),
    }


async def get_conversion_metrics(period: str = "30d", channel: str | None = None) -> dict:
    """
    Calculate aggregate conversion metrics for the given period.

    period: 7d | 30d | 90d | all
    channel: filter by channel_source (optional)
    """
    cutoff: datetime | None = None
    if period != "all":
        days = int(period.rstrip("d"))
        cutoff = _now() - timedelta(days=days)

    def _query():
        q = supabase.table("leads").select(
            "id,status,channel,channel_source,proposal_sent_at,"
            "first_response_at,contract_signed_at,created_at"
        )
        if cutoff:
            q = q.gte("created_at", cutoff.isoformat())
        if channel:
            q = q.or_(f"channel.eq.{channel},channel_source.eq.{channel}")
        return q.execute()

    result = await asyncio.to_thread(_query)
    leads = result.data or []

    # Only count leads that have reached at least proposal stage
    # Portuguese status values: proposta_enviada, respondeu, cliente, perdido, fechado
    with_proposal = [lead for lead in leads if lead.get("proposal_sent_at")]
    converted = [lead for lead in with_proposal if lead.get("status") in ("cliente", "fechado")]
    lost = [lead for lead in with_proposal if lead.get("status") == "perdido"]
    active = [
        lead for lead in with_proposal
        if lead.get("status") not in ("cliente", "fechado", "perdido")
    ]

    total_proposals = len(with_proposal)
    conv_rate = round(len(converted) / total_proposals, 4) if total_proposals > 0 else 0.0

    # Average time to convert
    ttc_values: list[float] = []
    for lead in converted:
        if lead.get("proposal_sent_at") and lead.get("contract_signed_at"):
            try:
                sent = datetime.fromisoformat(lead["proposal_sent_at"].replace("Z", "+00:00"))
                signed = datetime.fromisoformat(lead["contract_signed_at"].replace("Z", "+00:00"))
                ttc_values.append((signed - sent).total_seconds() / 86400)
            except Exception:
                pass

    avg_ttc = round(sum(ttc_values) / len(ttc_values), 2) if ttc_values else None

    # Average time to first response
    ttr_values: list[float] = []
    for lead in with_proposal:
        if lead.get("proposal_sent_at") and lead.get("first_response_at"):
            try:
                sent = datetime.fromisoformat(lead["proposal_sent_at"].replace("Z", "+00:00"))
                resp = datetime.fromisoformat(lead["first_response_at"].replace("Z", "+00:00"))
                ttr_values.append((resp - sent).total_seconds() / 86400)
            except Exception:
                pass

    avg_ttr = round(sum(ttr_values) / len(ttr_values), 2) if ttr_values else None

    # By channel breakdown
    by_channel: dict[str, dict] = {}
    for lead in with_proposal:
        ch = lead.get("channel_source") or lead.get("channel") or "unknown"
        if ch not in by_channel:
            by_channel[ch] = {"proposals": 0, "converted": 0, "lost": 0}
        by_channel[ch]["proposals"] += 1
        if lead.get("status") in ("cliente", "fechado"):
            by_channel[ch]["converted"] += 1
        elif lead.get("status") == "perdido":
            by_channel[ch]["lost"] += 1

    return {
        "period": period,
        "channel_filter": channel,
        "total_proposals": total_proposals,
        "converted": len(converted),
        "lost": len(lost),
        "active": len(active),
        "conversion_rate": conv_rate,
        "avg_time_to_convert_days": avg_ttc,
        "avg_time_to_first_response_days": avg_ttr,
        "by_channel": by_channel,
    }


async def check_stale_proposals(stale_days: int = 7) -> list[dict]:
    """
    Find proposals sent >= stale_days ago with no first_response_at yet.
    Returns list of lead dicts with days_since_proposal attached.
    """
    cutoff = (_now() - timedelta(days=stale_days)).isoformat()

    result = await asyncio.to_thread(
        lambda: supabase.table("leads")
        .select(
            "id,name,business_name,phone,channel,channel_source,"
            "proposal_sent_at,first_response_at,status,updated_at,touchpoints_count"
        )
        .lte("proposal_sent_at", cutoff)
        .is_("first_response_at", "null")
        .not_.in_("status", ["cliente", "fechado", "perdido"])
        .execute()
    )

    leads = result.data or []
    enriched = []
    for lead in leads:
        try:
            sent = datetime.fromisoformat(lead["proposal_sent_at"].replace("Z", "+00:00"))
            days_stale = (_now() - sent).days
        except Exception:
            days_stale = stale_days
        enriched.append({**lead, "days_since_proposal": days_stale})

    logger.info(
        "[conversion] check_stale_proposals: %d stale leads (>%dd)",
        len(enriched), stale_days,
    )
    return enriched
