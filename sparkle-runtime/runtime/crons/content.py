"""
Content Engine crons — CONTENT-1.12 / CONTENT-2.2.

Scheduled jobs for the content pipeline:

  content_pipeline_tick    (every 5 min)  — advance pieces in generating states
  content_publisher_tick   (every hour)   — publish scheduled pieces whose slot has arrived
  content_brain_sync       (daily 03h BRT) — ingest published pieces missing brain_chunk_id
  content_stuck_check      (every 30 min) — detect stuck pieces and retry or fail permanently

All jobs follow the same pattern as other Sparkle crons:
  - @log_cron decorator for cron_executions tracking
  - try/except per piece (one error doesn't stop others)
  - registered in start_scheduler() via register_content_jobs()

Friday notifications:
  - pending_approval: triggered by pipeline.py friday_notify_pending_approval() (AC5/AC6)
  - publish_failed: triggered by publisher.py (AC8)
  - permanent_failure: triggered by _run_content_stuck_check (CONTENT-2.2 AC5)
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


# ── CONTENT-2.2: Stuck pieces check (every 30 min) ─────────────

# Mapeamento: status travado → status de onde o retry deve reiniciar
_STUCK_RETRY_FROM: dict[str, str] = {
    "image_generating": "briefed",
    "video_generating": "image_done",
    "copy_generating":  "image_done",
}

# Status de falha permanente conforme domínio
_STUCK_FAILED_STATUS: dict[str, str] = {
    "image_generating": "image_failed",
    "video_generating": "video_failed",
    "copy_generating":  "video_failed",
}


@log_cron("content_stuck_check")
async def _run_content_stuck_check() -> None:
    """
    CONTENT-2.2: Detect stuck pieces and retry automatically (max 3x) or mark as failed_permanent.

    AC2: Selects pieces in generating states past pipeline_timeout_minutes threshold.
    AC3: Optimistic lock UPDATE — if 0 rows affected, pipeline_tick already moved the piece → skip.
    AC4: Calls advance_pipeline() immediately after a successful retry reset.
    AC5: retry_count >= 3 → failed_permanent=TRUE + Friday notification.
    AC6: Threshold read from settings.pipeline_timeout_minutes (env PIPELINE_TIMEOUT_MINUTES, default 20).
    """
    from runtime.config import settings
    from runtime.content.pipeline import advance_pipeline as _advance

    timeout_minutes = settings.pipeline_timeout_minutes
    stuck_statuses = list(_STUCK_RETRY_FROM.keys())

    # AC2: Build threshold timestamp in Python (Supabase client doesn't support raw interval)
    from datetime import datetime, timedelta, timezone
    threshold_dt = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    threshold_iso = threshold_dt.isoformat()

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("content_pieces")
            .select("*")
            .in_("status", stuck_statuses)
            .lt("updated_at", threshold_iso)
            .eq("failed_permanent", False)
            .execute()
        )
        pieces = result.data or []
    except Exception as exc:
        print(f"[content_cron:stuck_check] DB query failed: {exc}")
        return

    if not pieces:
        print(f"[content_cron:stuck_check] no stuck pieces found (threshold: {timeout_minutes}m)")
        return

    print(f"[content_cron:stuck_check] found {len(pieces)} stuck piece(s) (threshold: {timeout_minutes}m)")

    for piece in pieces:
        piece_id = piece.get("id", "?")
        current_status = piece.get("status", "")
        retry_count = piece.get("retry_count", 0)
        updated_at = piece.get("updated_at")

        try:
            if retry_count < 3:
                # AC3: Retry with optimistic lock
                retry_status = _STUCK_RETRY_FROM.get(current_status, "briefed")
                update_result = await asyncio.to_thread(
                    lambda pid=piece_id, cs=current_status, rs=retry_status, rc=retry_count, ua=updated_at: (
                        supabase.table("content_pieces")
                        .update({
                            "status": rs,
                            "retry_count": rc + 1,
                            "error_reason": "timeout_auto_retry",
                            "updated_at": _now_iso(),
                        })
                        .eq("id", pid)
                        .eq("status", cs)        # optimistic lock: status unchanged
                        .eq("updated_at", ua)    # optimistic lock: updated_at unchanged
                        .execute()
                    )
                )

                if not update_result.data:
                    # AC3: 0 rows affected — pipeline_tick already moved this piece
                    print(f"[content_cron:stuck_check] {piece_id[:8]} skipped (optimistic lock — already advanced)")
                    continue

                print(
                    f"[content_cron:stuck_check] {piece_id[:8]} retry #{retry_count + 1}: "
                    f"{current_status} → {retry_status}"
                )

                # AC4: Advance pipeline immediately after reset
                fresh_result = await asyncio.to_thread(
                    lambda pid=piece_id: supabase.table("content_pieces")
                    .select("*")
                    .eq("id", pid)
                    .limit(1)
                    .execute()
                )
                fresh_piece = (fresh_result.data or [None])[0]
                if fresh_piece:
                    await _advance(fresh_piece)

            else:
                # AC5: Max retries exceeded → permanent failure
                failed_status = _STUCK_FAILED_STATUS.get(current_status, "image_failed")

                await asyncio.to_thread(
                    lambda pid=piece_id, fs=failed_status: (
                        supabase.table("content_pieces")
                        .update({
                            "status": fs,
                            "failed_permanent": True,
                            "error_reason": "max_retries_exceeded",
                            "updated_at": _now_iso(),
                        })
                        .eq("id", pid)
                        .execute()
                    )
                )

                print(
                    f"[content_cron:stuck_check] {piece_id[:8]} PERMANENT FAILURE "
                    f"(retry_count={retry_count}, status={failed_status})"
                )

                # AC5: Notify Friday about permanent failure
                await _notify_friday_permanent_failure(piece_id, retry_count)

        except Exception as exc:
            print(f"[content_cron:stuck_check] error processing piece {piece_id[:8]}: {exc}")


async def _notify_friday_permanent_failure(piece_id: str, retry_count: int) -> None:
    """
    AC5: Send WhatsApp notification to Mauro about a permanently failed piece.
    Non-blocking — errors are caught and logged.
    """
    try:
        from runtime.config import settings
        from runtime.integrations import zapi

        phone = settings.mauro_whatsapp
        if not phone:
            print(f"[content_cron:stuck_check] MAURO_WHATSAPP not configured — skip failure notify for {piece_id[:8]}")
            return

        msg = (
            f"\u26a0\ufe0f Piece {piece_id[:8]} atingiu limite de retries ({retry_count}). "
            f"Falha permanente no pipeline de conte\u00fado. Verifique no Portal."
        )
        await asyncio.to_thread(lambda: zapi.send_text(phone, msg))
        print(f"[content_cron:stuck_check] Friday notified: permanent failure on piece {piece_id[:8]}")

    except Exception as exc:
        print(f"[content_cron:stuck_check] friday notify error (non-blocking): {exc}")


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

    # CONTENT-2.2 AC7: content_stuck_check every 30 minutes
    scheduler.add_job(
        _run_content_stuck_check,
        trigger=IntervalTrigger(minutes=30),
        id="content_stuck_check",
        replace_existing=True,
    )

    print("[content_crons] Registered: content_pipeline_tick, content_publisher_tick, content_brain_sync, content_stuck_check")
