"""
LIFECYCLE-2.3 - Stale Proposal Detector.

Daily cron job that:
  - Finds proposals with no response for 7+ days -> sends last-attempt WhatsApp via Z-API
  - Finds proposals with no response for 10+ days -> marks lead as lost (loss_reason: no_response)

Called by scheduler.py (daily at 11h BRT).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.pipeline.conversion import check_stale_proposals, _update_lead

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


# Thresholds (days without response after proposal)
LAST_ATTEMPT_THRESHOLD = 7   # days -> send last-attempt WhatsApp message
AUTO_LOST_THRESHOLD = 10     # days -> mark as lost automatically

_LAST_ATTEMPT_MSG = (
    "Ola {name}! Estamos encerrando o processo de proposta em breve. "
    "Caso ainda tenha interesse em automatizar o atendimento da {business}, "
    "estou a disposicao para conversar. Abracos, Sparkle AI"
)


async def _send_last_attempt(lead: dict) -> bool:
    """Send a last-attempt WhatsApp message via Z-API. Returns True on success."""
    phone = lead.get("phone", "").strip()
    if not phone:
        logger.warning(
            "[stale_detector] lead %s has no phone -- skipping Z-API send", lead["id"]
        )
        return False

    # Normalize: digits only
    phone_clean = "".join(c for c in phone if c.isdigit())
    if not phone_clean:
        return False

    name = lead.get("name") or lead.get("business_name") or "prezado"
    business = lead.get("business_name") or "sua empresa"
    message = _LAST_ATTEMPT_MSG.format(name=name.split()[0], business=business)

    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(lambda: send_text(phone_clean, message))
        logger.info(
            "[stale_detector] last-attempt sent to lead %s (%s)", lead["id"], phone_clean
        )
        return True
    except Exception as exc:
        logger.error(
            "[stale_detector] Z-API send failed for lead %s: %s", lead["id"], exc
        )
        return False


async def run_stale_detection() -> dict:
    """
    Main entrypoint called by daily cron.

    Flow:
      1. Fetch all proposals stale >= LAST_ATTEMPT_THRESHOLD days (no first_response_at).
      2. 10+ days -> mark as lost (loss_reason=no_response).
      3. 7-9 days -> send last-attempt WhatsApp (skip if already attempted today).

    Returns summary dict:
      {total_stale, last_attempt_sent, marked_lost, errors}
    """
    stale_leads = await check_stale_proposals(stale_days=LAST_ATTEMPT_THRESHOLD)

    last_attempt_sent = 0
    marked_lost = 0
    errors = 0

    for lead in stale_leads:
        days = lead.get("days_since_proposal", 0)
        lead_id = lead["id"]

        try:
            if days >= AUTO_LOST_THRESHOLD:
                await _update_lead(lead_id, {
                    "status": "perdido",
                    "loss_reason": "no_response",
                })
                marked_lost += 1
                logger.info(
                    "[stale_detector] lead %s marked lost after %d days without response",
                    lead_id, days,
                )

            elif days >= LAST_ATTEMPT_THRESHOLD:
                # Avoid double-sending: skip if updated_at is today
                updated_at_raw = lead.get("updated_at", "")
                already_attempted_today = False
                if updated_at_raw:
                    try:
                        updated_at = datetime.fromisoformat(
                            updated_at_raw.replace("Z", "+00:00")
                        )
                        already_attempted_today = updated_at.date() == _now().date()
                    except Exception:
                        pass

                if not already_attempted_today:
                    sent = await _send_last_attempt(lead)
                    if sent:
                        # Bump touchpoints_count + updated_at to prevent re-send today
                        await _update_lead(lead_id, {
                            "touchpoints_count": (lead.get("touchpoints_count") or 0) + 1,
                        })
                        last_attempt_sent += 1
                else:
                    logger.debug(
                        "[stale_detector] lead %s already attempted today -- skip", lead_id
                    )

        except Exception as exc:
            logger.error("[stale_detector] error processing lead %s: %s", lead_id, exc)
            errors += 1

    summary = {
        "total_stale": len(stale_leads),
        "last_attempt_sent": last_attempt_sent,
        "marked_lost": marked_lost,
        "errors": errors,
    }
    logger.info("[stale_detector] run complete: %s", summary)
    return summary
