"""
Content Engine crons — CONTENT-1.12.

Three scheduled jobs for the content pipeline:

  content_pipeline_tick    (every 5 min)  — advance pieces in generating states
  content_publisher_tick   (every hour)   — publish scheduled pieces whose slot has arrived
  content_brain_sync       (daily 03h BRT) — ingest published pieces missing brain_chunk_id

All jobs follow the same pattern as other Sparkle crons:
  - @log_cron decorator for cron_executions tracking
  - try/except per piece (AC4: one error doesn't stop others)
  - registered in start_scheduler() via register_content_jobs()

Friday notifications:
  - pending_approval: triggered by pipeline.py friday_notify_pending_approval() (AC5/AC6)
  - publish_failed: triggered by publisher.py (AC8)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from runtime.cron_logger import log_cron
from runtime.db import supabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── CONTENT-1.12 AC1: Pipeline tick (every 5 min) ──────────────

@log_cron("content_pipeline_tick")
async def _run_content_pipeline_tick() -> None:
    """
    AC1: Find pieces in image_generating or video_generating and advance them.
    Piece-level try/except ensures one failure doesn't stop others (AC4).
    """
    from runtime.content.pipeline import advance_pipeline as _advance

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("content_pieces")
            .select("*")
            .in_("status", ["image_generating", "video_generating"])
            .execute()
        )
        pieces = result.data or []
    except Exception as exc:
        print(f"[content_cron:pipeline_tick] DB query failed: {exc}")
        return

    if not pieces:
        return

    print(f"[content_cron:pipeline_tick] processing {len(pieces)} piece(s)")

    for piece in pieces:
        try:
            await _advance(piece)
        except Exception as exc:
            print(
                f"[content_cron:pipeline_tick] error on piece {piece.get('id', '?')[:8]}: {exc}"
            )


# ── CONTENT-1.12 AC2: Publisher tick (every hour) ──────────────

@log_cron("content_publisher_tick")
async def _run_content_publisher_tick() -> None:
    """
    AC2: Find scheduled pieces whose scheduled_at <= now() and publish them.
    AC4: Piece-level try/except.
    """
    from runtime.content.publisher import publish as _publish

    now = _now_iso()

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("content_pieces")
            .select("*")
            .eq("status", "scheduled")
            .lte("scheduled_at", now)
            .execute()
        )
        pieces = result.data or []
    except Exception as exc:
        print(f"[content_cron:publisher_tick] DB query failed: {exc}")
        return

    if not pieces:
        return

    print(f"[content_cron:publisher_tick] publishing {len(pieces)} piece(s)")

    for piece in pieces:
        try:
            await _publish(piece)
        except Exception as exc:
            print(
                f"[content_cron:publisher_tick] error on piece {piece.get('id', '?')[:8]}: {exc}"
            )


# ── CONTENT-1.12 AC3: Brain sync (daily 03h BRT) ───────────────

@log_cron("content_brain_sync")
async def _run_content_brain_sync() -> None:
    """
    AC3: Find published pieces with brain_chunk_id IS NULL and ingest them.
    AC4: Piece-level try/except.
    """
    from runtime.content.publisher import _ingest_published_to_brain as _ingest
    from runtime.content.publisher import _update_piece as _upd

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("content_pieces")
            .select("*")
            .eq("status", "published")
            .is_("brain_chunk_id", "null")
            .limit(50)
            .execute()
        )
        pieces = result.data or []
    except Exception as exc:
        print(f"[content_cron:brain_sync] DB query failed: {exc}")
        return

    if not pieces:
        return

    print(f"[content_cron:brain_sync] syncing {len(pieces)} published piece(s) to Brain")

    for piece in pieces:
        piece_id = piece.get("id", "?")
        try:
            chunk_id = await _ingest(piece)
            if chunk_id:
                _upd(piece_id, {"brain_chunk_id": chunk_id})
                print(f"[content_cron:brain_sync] {piece_id[:8]} -> chunk {chunk_id}")
            else:
                print(f"[content_cron:brain_sync] {piece_id[:8]} — ingest returned no chunk_id")
        except Exception as exc:
            print(f"[content_cron:brain_sync] error on piece {piece_id[:8]}: {exc}")


# ── Job registration ────────────────────────────────────────────

def register_content_jobs(scheduler) -> None:
    """
    Register all content crons on the given APScheduler instance.
    Called from scheduler.py start_scheduler().
    """
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("America/Sao_Paulo")

    # AC1: content_pipeline_tick every 5 minutes
    scheduler.add_job(
        _run_content_pipeline_tick,
        trigger=IntervalTrigger(minutes=5),
        id="content_pipeline_tick",
        replace_existing=True,
    )

    # AC2: content_publisher_tick every hour (at minute 0)
    scheduler.add_job(
        _run_content_publisher_tick,
        trigger=CronTrigger(minute=0),
        id="content_publisher_tick",
        replace_existing=True,
    )

    # AC3: content_brain_sync daily at 03h BRT (= 06h UTC)
    scheduler.add_job(
        _run_content_brain_sync,
        trigger=CronTrigger(hour=3, minute=0, timezone=_TZ),
        id="content_brain_sync",
        replace_existing=True,
    )

    print("[content_crons] Registered: content_pipeline_tick, content_publisher_tick, content_brain_sync")
