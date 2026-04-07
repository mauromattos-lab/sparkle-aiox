"""
Content Pipeline Orchestrator — CONTENT-1.6.

State machine that advances content_pieces through the MVP pipeline:

  briefed → image_generating → image_done
          → (copy + video in parallel) → video_done
          → [ip_audit] → pending_approval
          → approved/rejected → scheduled → published

Assembly (Creatomate) and automatic TTS are REMOVED from MVP v1.1.
Voice is applied manually by Mauro.

Concurrency limit: max 5 pieces simultaneously in image_generating
or video_generating.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase

# ── Constants ──────────────────────────────────────────────────

MAX_CONCURRENT = 5  # max pieces in image_generating or video_generating

TERMINAL_STATUSES = {
    "pending_approval", "approved", "rejected", "scheduled", "published",
    "image_failed", "video_failed", "copy_failed",
}

FAILED_STATUSES = {"image_failed", "video_failed", "copy_failed"}

# Map: failed status → status to retry from
RETRY_FROM: dict[str, str] = {
    "image_failed": "briefed",
    "video_failed": "image_done",
    "copy_failed": "image_done",
}


# ── Helpers ────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _get_piece(piece_id: str) -> dict | None:
    result = supabase.table("content_pieces").select("*").eq("id", piece_id).limit(1).execute()
    return result.data[0] if result.data else None


def _set_status(piece_id: str, new_status: str) -> None:
    """Transition piece to new_status, appending entry to pipeline_log."""
    piece = _get_piece(piece_id)
    if not piece:
        return

    log_entry = {
        "from": piece.get("status"),
        "to": new_status,
        "at": _now_iso(),
    }
    pipeline_log = list(piece.get("pipeline_log") or [])
    pipeline_log.append(log_entry)

    supabase.table("content_pieces").update({
        "status": new_status,
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()

    print(f"[pipeline] {piece_id[:8]} {log_entry['from']} → {new_status}")


def _update_piece(piece_id: str, fields: dict) -> None:
    """Partial update on content_pieces (no status transition)."""
    supabase.table("content_pieces").update({
        **fields,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()


def _log_pipeline_event(piece_id: str, event: dict) -> None:
    """Append an arbitrary event dict to pipeline_log (no status change)."""
    piece = _get_piece(piece_id)
    if not piece:
        return
    pipeline_log = list(piece.get("pipeline_log") or [])
    pipeline_log.append({**event, "at": _now_iso()})
    supabase.table("content_pieces").update({
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()


def can_start_production() -> bool:
    """Return True if fewer than MAX_CONCURRENT pieces are in active generation."""
    try:
        result = (
            supabase.table("content_pieces")
            .select("id", count="exact")
            .in_("status", ["image_generating", "video_generating"])
            .execute()
        )
        count = result.count if result.count is not None else len(result.data or [])
        return count < MAX_CONCURRENT
    except Exception as exc:
        print(f"[pipeline] can_start_production error: {exc}")
        return False


# ── Step implementations ───────────────────────────────────────

async def _step_image(piece: dict) -> bool:
    """
    briefed → image_generating → image_done

    Returns True on success, False on failure (status set to image_failed).
    """
    from runtime.content.image_engineer import prepare_generation, build_prompt, get_tier_a_reference
    from runtime.content.image_generator import generate_image_for_piece

    piece_id = piece["id"]
    theme = piece.get("theme", "")
    mood = piece.get("mood", "inspirador")
    style = piece.get("style", "influencer_natural")

    _set_status(piece_id, "image_generating")

    try:
        gen_data = await prepare_generation(piece_id, theme, mood, style)
        ref_url = gen_data["reference"].get("storage_path") or gen_data["reference"].get("image_url")
        image_url = await generate_image_for_piece(
            content_piece_id=piece_id,
            prompt=gen_data["prompt"],
            reference_image_url=ref_url,
        )
        if image_url is None:
            raise RuntimeError("generate_image_for_piece returned None")

        _update_piece(piece_id, {"image_url": image_url})
        _set_status(piece_id, "image_done")
        return True

    except Exception as exc:
        print(f"[pipeline] image step failed for {piece_id}: {exc}")
        _log_pipeline_event(piece_id, {"event": "image_error", "error": str(exc)})
        _set_status(piece_id, "image_failed")
        return False


async def _step_video(piece: dict) -> bool:
    """Generate video from image_url. Updates video_url if successful."""
    from runtime.content.video_engineer import build_video_prompt
    from runtime.content.video_generator import generate_video_for_piece

    piece_id = piece["id"]
    image_url = piece.get("image_url")
    style = piece.get("style", "influencer_natural")
    theme = piece.get("theme", "")

    if not image_url:
        print(f"[pipeline] video step skipped — no image_url for {piece_id}")
        return False

    try:
        _set_status(piece_id, "video_generating")
        prompt = build_video_prompt(style, theme)
        video_url = await generate_video_for_piece(
            content_piece_id=piece_id,
            image_url=image_url,
            prompt=prompt,
            style=style,
        )
        if video_url is None:
            raise RuntimeError("generate_video_for_piece returned None")

        _update_piece(piece_id, {"video_url": video_url})
        return True

    except Exception as exc:
        print(f"[pipeline] video step failed for {piece_id}: {exc}")
        _log_pipeline_event(piece_id, {"event": "video_error", "error": str(exc)})
        _set_status(piece_id, "video_failed")
        return False


async def _step_copy(piece: dict) -> bool:
    """Generate caption + voice_script. Updates content_pieces fields."""
    from runtime.content.copy_specialist import apply_copy_to_piece
    from runtime.config import settings

    piece_id = piece["id"]
    theme = piece.get("theme", "")
    mood = piece.get("mood", "inspirador")
    style = piece.get("style", "minimalista")
    platform = piece.get("platform", "instagram")
    # content_pieces uses creator_id not client_id; fall back to internal id for LLM billing
    client_id = piece.get("creator_id") or settings.sparkle_internal_client_id

    try:
        await apply_copy_to_piece(
            content_piece_id=piece_id,
            theme=theme,
            mood=mood,
            style=style,
            platform=platform,
            include_narration=False,  # MVP: no TTS, voice manual
            client_id=client_id,
        )
        return True

    except Exception as exc:
        print(f"[pipeline] copy step failed for {piece_id}: {exc}")
        _log_pipeline_event(piece_id, {"event": "copy_error", "error": str(exc)})
        _set_status(piece_id, "copy_failed")
        return False


async def _step_parallel(piece: dict) -> bool:
    """
    image_done → run video + copy in parallel → video_done.

    Both tasks run concurrently. If video fails, status = video_failed.
    Copy failure is non-blocking (just logs, pipeline continues).
    """
    piece_id = piece["id"]
    # Re-fetch to get current image_url in case it was updated
    fresh = _get_piece(piece_id)
    if not fresh:
        return False

    video_task = asyncio.create_task(_step_video(fresh))
    copy_task = asyncio.create_task(_step_copy(fresh))

    results = await asyncio.gather(video_task, copy_task, return_exceptions=True)
    video_ok = results[0] if not isinstance(results[0], Exception) else False
    copy_ok = results[1] if not isinstance(results[1], Exception) else False

    if not video_ok:
        # video failure already set status to video_failed
        print(f"[pipeline] parallel: video failed for {piece_id}")
        return False

    # If copy failed but video succeeded, log but continue (copy can be retried)
    if not copy_ok:
        print(f"[pipeline] parallel: copy failed for {piece_id} — continuing pipeline")
        _log_pipeline_event(piece_id, {"event": "copy_warning", "message": "copy failed but pipeline continues"})

    _set_status(piece_id, "video_done")
    return True


async def _step_audit(piece: dict) -> None:
    """
    Run IP Auditor between video_done and pending_approval.
    Never blocks — always advances.
    """
    try:
        from runtime.content.ip_auditor import audit_piece
        await audit_piece(piece)
    except Exception as exc:
        print(f"[pipeline] ip_audit step error (non-blocking): {exc}")
        _log_pipeline_event(piece["id"], {
            "event": "ip_audit_error",
            "error": str(exc),
            "note": "audit failed but pipeline continued",
        })


# ── Main orchestrator ──────────────────────────────────────────

async def advance_pipeline(piece: dict) -> None:
    """
    Advance a content_piece by one or more steps based on its current status.

    This function is idempotent — calling it multiple times on the same piece
    in the same state is safe. It handles one "tick" of the pipeline.

    Flow:
      briefed       → _step_image (sets image_generating → image_done)
      image_done    → _step_parallel (copy + video) → video_done
      video_done    → _step_audit → pending_approval
    """
    status = piece.get("status")
    piece_id = piece["id"]

    if status == "briefed":
        if not can_start_production():
            print(f"[pipeline] concurrency limit reached — {piece_id} waiting")
            return
        await _step_image(piece)

    elif status == "image_done":
        if not can_start_production():
            print(f"[pipeline] concurrency limit reached — {piece_id} waiting")
            return
        await _step_parallel(piece)

    elif status == "video_done":
        # IP Audit then advance to pending_approval
        await _step_audit(piece)
        # Re-fetch after audit (audit may have written to pipeline_log)
        fresh = _get_piece(piece_id)
        if fresh and fresh.get("status") == "video_done":
            _set_status(piece_id, "pending_approval")

    elif status in TERMINAL_STATUSES:
        print(f"[pipeline] {piece_id} is in terminal status '{status}' — skipping")

    else:
        print(f"[pipeline] {piece_id} unknown status '{status}' — skipping")


async def retry_piece(piece_id: str) -> dict:
    """
    Restart a piece from its failed step.

    Returns updated piece dict or raises ValueError if not in a failed state.
    """
    piece = _get_piece(piece_id)
    if not piece:
        raise ValueError(f"content_piece {piece_id} not found")

    status = piece.get("status")
    if status not in FAILED_STATUSES:
        raise ValueError(f"Piece {piece_id} is not in a failed state (status='{status}')")

    retry_status = RETRY_FROM.get(status, "briefed")
    _set_status(piece_id, retry_status)

    # Re-fetch and advance
    fresh = _get_piece(piece_id)
    if fresh:
        asyncio.create_task(advance_pipeline(fresh))

    return _get_piece(piece_id) or {}


async def tick_pipeline() -> dict:
    """
    Cron tick — called every 5 minutes by the scheduler.

    Advances all pieces stuck in non-terminal, non-generating states.
    Also polls generating pieces to check if external providers have finished.
    """
    result = {
        "advanced": [],
        "skipped": [],
        "errors": [],
    }

    # 1. Find pieces that need advancing
    advanceable = supabase.table("content_pieces").select("*").in_(
        "status", ["briefed", "image_done", "video_done"]
    ).execute()

    for piece in (advanceable.data or []):
        try:
            await advance_pipeline(piece)
            result["advanced"].append(piece["id"])
        except Exception as exc:
            result["errors"].append({"id": piece["id"], "error": str(exc)})

    # 2. Poll generating pieces (for async providers like Kling)
    # Currently Gemini/Veo are synchronous — this is a hook for future async providers
    generating = supabase.table("content_pieces").select("id, status").in_(
        "status", ["image_generating", "video_generating"]
    ).execute()

    if generating.data:
        print(f"[pipeline:tick] {len(generating.data)} pieces currently generating (provider-side)")
        for p in generating.data:
            result["skipped"].append(p["id"])

    return result
