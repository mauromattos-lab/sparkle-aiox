"""
Content Approval — CONTENT-1.6.

Logic for approving and rejecting content_pieces after they reach
pending_approval status.

  pending_approval → approved   (with optional scheduled_at)
  pending_approval → rejected   (with reason)
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
    Approve a content_piece, optionally setting a scheduled publish date.

    Transitions: pending_approval → approved (→ scheduled if scheduled_at provided).

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

    # Build pipeline_log entry
    pipeline_log = list(piece.get("pipeline_log") or [])
    pipeline_log.append({
        "from": "pending_approval",
        "to": "approved",
        "at": _now_iso(),
    })

    fields: dict = {
        "status": "approved",
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }

    if scheduled_at:
        fields["scheduled_at"] = scheduled_at
        fields["status"] = "scheduled"
        # Replace the log entry for scheduled
        pipeline_log[-1]["to"] = "scheduled"

    supabase.table("content_pieces").update(fields).eq("id", piece_id).execute()
    return _get_piece(piece_id) or {}


def reject_piece(piece_id: str, reason: str = "") -> dict:
    """
    Reject a content_piece, recording the rejection reason.

    Transitions: pending_approval → rejected.

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
