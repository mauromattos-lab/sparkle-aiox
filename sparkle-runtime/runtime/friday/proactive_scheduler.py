"""
Friday Proactive Scheduler — B3-02.

Registers periodic proactive-check jobs with the main APScheduler.
Runs every 30 minutes during work hours (7h-22h SP).

Called from the main scheduler's start_scheduler() function,
following the same pattern as runtime/characters/scheduler.py.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_proactive_check() -> None:
    """
    Periodic job: evaluate all proactive triggers and send messages
    that pass anti-spam checks.

    Errors are logged but never propagate — the scheduler must not crash.
    """
    from runtime.config import settings

    if not settings.proactive_enabled:
        logger.info("[FRIDAY-PROACTIVE] Desativado — aguardando redesign Wave 1 (W1-FRIDAY-1)")
        return

    from runtime.friday.proactive import check_proactive_triggers

    try:
        results = await check_proactive_triggers()
        sent = [r for r in results if r.get("status") == "sent"]
        if sent:
            logger.info("proactive_check: %d message(s) sent", len(sent))
    except Exception as e:
        logger.error("proactive_check: unhandled error — %s", e)


def register_proactive_jobs(scheduler) -> None:
    """
    Register Friday proactive jobs with the APScheduler instance.

    Args:
        scheduler: The APScheduler AsyncIOScheduler instance.
    """
    from runtime.config import settings

    if not settings.proactive_enabled:
        logger.info("[FRIDAY-PROACTIVE] Desativado — job não registrado. Aguardando redesign Wave 1 (W1-FRIDAY-1)")
        return

    from apscheduler.triggers.cron import CronTrigger
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("America/Sao_Paulo")

    # Run every 30 minutes from 7h to 21h30 SP (last run at 21:30, quiet at 22h)
    scheduler.add_job(
        run_proactive_check,
        trigger=CronTrigger(
            hour="7-21",
            minute="0,30",
            timezone=_TZ,
        ),
        id="friday_proactive_check",
        replace_existing=True,
    )
    logger.info("friday_proactive_check job registered (every 30 min, 7h-21h30 SP)")
