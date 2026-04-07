"""
Content Approval -- CONTENT-1.6 / CONTENT-1.11.

Logic for approving and rejecting content_pieces after they reach
pending_approval status.

CONTENT-1.11 AC1: approve_piece() auto-calculates scheduled_at using
get_next_slot() from publisher.py and transitions directly to 'scheduled'.

  pending_approval -> scheduled  (approve: auto-schedules next available slot)
  pending_approval -> rejected   (with reason)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_piece(piece_id: str) -> dict | None:
    result = supabase.table("content_pieces").select("*").eq("id", piece_id).limit(1).execute()
    return result.data[0] if result.data else None


def approve_piece(piece_id: str, scheduled_at: Optional[str] = None) -> dict:
    """
    Approve a content_piece and schedule it for publication.

    CONTENT-1.11 AC1: If scheduled_at is not provided, automatically calculates
    the next available publish slot (08h, 12h, or 18h BRT) that is not already
    occupied by another scheduled piece.

    Transitions: pending_approval -> scheduled

    Returns updated piece dict.
    Raises ValueError if piece not found or not in pending_approval.
    """
    piece = _get_piece(piece_id)
    if not piece:
        raise ValueError(f"content_piece {piece_id} not found")

    if piece.get("status") != "pending_approval":
        raise ValueError(
            f"Piece {piece_id} is not pending approval (status='{piece.get('status')}')"
        )

    # Calculate next slot if not provided (AC1)
    if not scheduled_at:
        from runtime.content.publisher import get_next_slot
        slot_dt = get_next_slot()
        scheduled_at = slot_dt.isoformat()

    # Build pipeline_log entry
    pipeline_log = list(piece.get("pipeline_log") or [])
    pipeline_log.append({
        "from": "pending_approval",
        "to": "scheduled",
        "at": _now_iso(),
        "scheduled_at": scheduled_at,
    })

    supabase.table("content_pieces").update({
        "status": "scheduled",
        "scheduled_at": scheduled_at,
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()

    return _get_piece(piece_id) or {}


def reject_piece(piece_id: str, reason: str = "") -> dict:
    """
    Reject a content_piece, recording the rejection reason.

    Transitions: pending_approval -> rejected.

    Returns updated piece dict.
    Raises ValueError if piece not found or not in pending_approval.
    """
    piece = _get_piece(piece_id)
    if not piece:
        raise ValueError(f"content_piece {piece_id} not found")

    if piece.get("status") != "pending_approval":
        raise ValueError(
            f"Piece {piece_id} is not pending approval (status='{piece.get('status')}')"
        )

    pipeline_log = list(piece.get("pipeline_log") or [])
    pipeline_log.append({
        "from": "pending_approval",
        "to": "rejected",
        "at": _now_iso(),
        "reason": reason,
    })

    supabase.table("content_pieces").update({
        "status": "rejected",
        "rejection_reason": reason,
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()

    return _get_piece(piece_id) or {}


def get_approval_queue(limit: int = 50) -> list[dict]:
    """
    Return all pieces in pending_approval status, newest first.
    This is the queue Mauro reviews.
    """
    result = (
        supabase.table("content_pieces")
        .select("*")
        .eq("status", "pending_approval")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
