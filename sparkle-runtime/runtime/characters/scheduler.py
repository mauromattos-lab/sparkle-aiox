"""
Character scheduler — B2-02.

Periodic background tasks for character state management:
  - time_passage every 30 minutes for all active characters
    (energy recovery toward baseline, extreme mood normalization)

Registers its jobs with the main APScheduler instance.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from runtime.db import supabase

logger = logging.getLogger(__name__)


async def run_character_time_passage() -> None:
    """
    Run time_passage event for all active characters.

    Called every 30 minutes by the scheduler.  For each character that
    has a row in character_state:
      1. Evaluate time_passage event via orchestrator
      2. Let the orchestrator handle energy recovery + mood decay

    Errors for individual characters are logged but do not stop processing
    of other characters.
    """
    from runtime.characters.orchestrator import evaluate_event

    try:
        # Fetch all character_state rows (one per active character)
        result = await asyncio.to_thread(
            lambda: supabase.table("character_state")
            .select("character_slug")
            .execute()
        )
        rows = result.data or []

        if not rows:
            logger.debug("character_time_passage: no character_state rows found — skip")
            return

        slugs = [r["character_slug"] for r in rows if r.get("character_slug")]
        logger.info("character_time_passage: processing %d characters", len(slugs))

        for slug in slugs:
            try:
                await evaluate_event(slug, "time_passage", {"triggered_by": "scheduler"})
            except Exception as e:
                logger.error("character_time_passage: error for '%s': %s", slug, e)

        logger.info("character_time_passage: completed for %d characters", len(slugs))

    except Exception as e:
        logger.error("character_time_passage: failed to fetch characters: %s", e)


def register_character_jobs(scheduler) -> None:
    """
    Register character-related periodic jobs with the APScheduler instance.

    Called from the main scheduler's start_scheduler() function.

    Args:
        scheduler: The APScheduler AsyncIOScheduler instance.
    """
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler.add_job(
        run_character_time_passage,
        trigger=IntervalTrigger(minutes=30),
        id="character_time_passage",
        replace_existing=True,
    )
    logger.info("character_time_passage job registered (every 30 min)")
