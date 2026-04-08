"""
Content Approval -- CONTENT-1.6 / CONTENT-1.11 / W1-BRAIN-1.

Logic for approving and rejecting content_pieces after they reach
pending_approval status.

CONTENT-1.11 AC1: approve_piece() auto-calculates scheduled_at using
get_next_slot() from publisher.py and transitions directly to 'scheduled'.

W1-BRAIN-1: approve_piece() fires a non-blocking Brain ingest after
transitioning to 'scheduled', so the flywheel works even when Instagram
credentials are not yet configured.

  pending_approval -> scheduled  (approve: auto-schedules next available slot)
  pending_approval -> rejected   (with reason)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx

from runtime.config import settings
from runtime.db import supabase

# Runtime base URL for internal calls
_RUNTIME_BASE = "http://localhost:8001"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_piece(piece_id: str) -> dict | None:
    result = supabase.table("content_pieces").select("*").eq("id", piece_id).limit(1).execute()
    return result.data[0] if result.data else None


def _update_piece(piece_id: str, fields: dict) -> None:
    supabase.table("content_pieces").update({
        **fields,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()


# ── Brain flywheel on approval ────────────────────────────────

async def _update_synthesis_after_ingest(piece: dict) -> None:
    """
    W2-BRAIN-1: Atualiza síntese do namespace após ingestão aprovada.
    Non-blocking — falha silenciosamente sem afetar o fluxo de aprovação.
    """
    try:
        from runtime.brain.synthesis import update_domain_synthesis
        # Content pieces sempre vão para sparkle-lore (namespace padrão para conteúdo)
        namespace = "sparkle-lore"
        await update_domain_synthesis(namespace)
    except Exception as e:
        print(f"[approval] synthesis update failed (non-blocking): {e}")


async def _ingest_approved_to_brain(piece: dict) -> None:
    """
    W1-BRAIN-1 AC1 (T3/T4): Non-blocking Brain ingest triggered on content approval.

    Fires the full 6-phase ingest pipeline so the flywheel works even when
    Instagram is not yet configured. Brain ingest happens at approval time,
    not publication time — guaranteeing lore accumulation regardless of publish status.

    Failures are logged as warnings and never block or revert the approval.
    """
    try:
        piece_id = piece["id"]
        theme = piece.get("theme") or ""
        caption = piece.get("caption") or ""
        voice_script = piece.get("voice_script") or ""
        character = (piece.get("character") or "zenya").lower()
        content_type = piece.get("content_type") or "reel"
        approved_at = piece.get("approved_at") or _now_iso()
        # instagram_url is null at approval time — will be updated by publisher if/when published
        instagram_url = piece.get("published_url") or "null"

        raw_content = (
            f"[Approved Reel] Theme: {theme}\n"
            f"Caption: {caption[:500]}\n"
            f"Script: {voice_script[:300]}"
        ).strip()

        if not raw_content:
            print(f"[approval] Brain ingest skipped for {piece_id[:8]}: empty content")
            return

        # metadata header embedded in raw_content so pipeline stores it in chunk_metadata
        metadata_header = (
            f"[metadata] content_piece_id={piece_id} "
            f"character={character} content_type={content_type} "
            f"approved_at={approved_at} instagram_url={instagram_url}"
        )

        payload = {
            "source_type": "published_reel",      # maps to sparkle-lore in namespace.py
            "raw_content": f"{metadata_header}\n{raw_content}",
            "title": f"Reel: {theme[:80]}",
            "persona": "especialista",             # brain_owner = "content"
            "client_id": None,                     # sparkle-internal
            "run_dna": False,
            "run_narrative": False,
        }

        headers = {}
        if settings.runtime_api_key:
            headers["X-API-Key"] = settings.runtime_api_key

        url = f"{_RUNTIME_BASE}/brain/ingest-pipeline"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            print(f"[approval] Brain ingest pipeline error {resp.status_code} for {piece_id[:8]}: {resp.text[:200]}")
            return

        data = resp.json()
        if data.get("status") != "ok":
            print(f"[approval] Brain ingest failed for {piece_id[:8]}: {data.get('error', 'unknown')}")
            return

        # Extract chunk_id and persist to content_pieces.brain_chunk_id (T5)
        chunk_ids = data.get("chunk_ids") or []
        chunk_id = chunk_ids[0] if chunk_ids else data.get("chunk_id")
        if chunk_id:
            try:
                _update_piece(piece_id, {"brain_chunk_id": chunk_id})
            except Exception as exc:
                print(f"[approval] brain_chunk_id update failed for {piece_id[:8]}: {exc}")

        print(f"[approval] Brain ingest (pipeline): piece {piece_id[:8]} → chunk {chunk_id} (namespace=sparkle-lore)")

    except Exception as exc:
        # Non-blocking: log warning but never raise
        import traceback
        print(f"[approval] Brain ingest warning for piece (non-blocking): {type(exc).__name__}: {exc}")
        print(f"[approval] Brain ingest traceback: {traceback.format_exc()[:500]}")


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
        "approved_at": _now_iso(),
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()

    # W1-BRAIN-1 AC1: Flywheel — trigger Brain ingest non-blocking at approval time.
    # Works regardless of Instagram configuration.
    fresh = _get_piece(piece_id)
    if fresh:
        try:
            # asyncio.get_running_loop() works when called from a sync function
            # running within an async context (FastAPI endpoint).
            loop = asyncio.get_running_loop()
            loop.create_task(_ingest_approved_to_brain(fresh))
            # W2-BRAIN-1: Update domain synthesis non-blocking after ingest
            loop.create_task(_update_synthesis_after_ingest(fresh))
        except RuntimeError:
            # No running event loop (e.g., called from sync context / tests)
            # Best-effort: fire and forget via thread-safe wrapper
            print(f"[approval] No running event loop for brain ingest — scheduling via asyncio.run")
            import threading
            threading.Thread(
                target=lambda: asyncio.run(_ingest_approved_to_brain(fresh)),
                daemon=True,
            ).start()
        except Exception as exc:
            print(f"[approval] Brain ingest task creation failed (non-blocking): {exc}")

    return fresh or {}


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


def _compute_audit_badge(piece: dict) -> dict:
    """
    W1-CHAR-1 AC-6: Compute audit badge from pipeline_log for Portal HQ display.

    Badge structure:
    {
        "status": "lore_ok" | "lore_warning" | "skipped" | "pending",
        "label": str,         # Human-readable label for Portal badge
        "lore_compliance": "COMPATIVEL" | "INCOMPATIVEL" | "SKIPPED" | null,
        "lore_compliance_reason": str | null,
        "warnings": list[str],
        "lore_chunks_used": int,
        "character_lore_entries_used": int,
    }
    """
    log = piece.get("pipeline_log") or []
    audit_entries = [e for e in log if e.get("event") == "ip_audit"]

    if not audit_entries:
        return {
            "status": "pending",
            "label": "Auditoria Pendente",
            "lore_compliance": None,
            "lore_compliance_reason": None,
            "warnings": [],
            "lore_chunks_used": 0,
            "character_lore_entries_used": 0,
        }

    # Use the most recent audit entry
    audit = audit_entries[-1].get("ip_audit", {})
    warnings = audit.get("warnings", [])
    compliance = audit.get("lore_compliance", "SKIPPED")

    if compliance == "SKIPPED" and not warnings:
        status = "skipped"
        label = "Auditoria Skipped"
    elif warnings or compliance == "INCOMPATIVEL":
        status = "lore_warning"
        label = f"Lore: Warning ({len(warnings)} aviso(s))"
    else:
        status = "lore_ok"
        label = "Lore OK"

    return {
        "status": status,
        "label": label,
        "lore_compliance": compliance,
        "lore_compliance_reason": audit.get("lore_compliance_reason"),
        "warnings": warnings,
        "lore_chunks_used": audit.get("lore_chunks_used", 0),
        "character_lore_entries_used": audit.get("character_lore_entries_used", 0),
    }


def get_approval_queue(limit: int = 50) -> list[dict]:
    """
    Return all pieces in pending_approval status, newest first.
    This is the queue Mauro reviews.

    W1-CHAR-1 AC-6: Each piece includes an 'audit_badge' field computed from
    pipeline_log, so the Portal HQ can display lore compliance status visually.
    """
    result = (
        supabase.table("content_pieces")
        .select("*")
        .eq("status", "pending_approval")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    pieces = result.data or []

    # Attach audit badge to each piece (AC-6)
    for piece in pieces:
        piece["audit_badge"] = _compute_audit_badge(piece)

    return pieces
