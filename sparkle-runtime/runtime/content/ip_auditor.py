"""
IP Auditor — CONTENT-1.10.

Validates content_pieces against Zenya's lore (Brain namespace 'sparkle-lore')
and checks for repetition against recently published pieces.

Rules:
  - Always advances — NEVER blocks the pipeline
  - Warnings are written to pipeline_log under 'ip_audit' key
  - Lore check: queries Brain for restriction-tagged chunks
  - Repetition check: fuzzy-match against pieces published in last 7 days

Called by pipeline.py between video_done and pending_approval.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase

# Fuzzy match threshold for repetition detection (0-100)
REPETITION_THRESHOLD = 80


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ── Brain query ────────────────────────────────────────────────

async def _query_sparkle_lore(query_text: str, top_k: int = 5) -> list[dict]:
    """
    Query Brain namespace 'sparkle-lore' for chunks relevant to query_text.

    Returns list of chunk dicts with keys: content, tags (or metadata), similarity.
    Gracefully returns [] on any error — auditor never blocks.
    """
    try:
        from runtime.brain.embedding import get_embedding

        embedding = await get_embedding(query_text)
        if not embedding:
            print("[ip_auditor] embedding unavailable — skipping lore check")
            return []

        # Query brain_chunks filtered by namespace = sparkle-lore
        result = await asyncio.to_thread(
            lambda: supabase.rpc(
                "match_brain_chunks",
                {
                    "query_embedding": embedding,
                    "pipeline_type_in": "especialista",
                    "client_id_in": None,
                    "match_count": top_k,
                },
            ).execute()
        )

        chunks = result.data or []

        # Filter to sparkle-lore namespace
        lore_chunks = [
            c for c in chunks
            if (c.get("namespace") == "sparkle-lore"
                or (c.get("chunk_metadata") or {}).get("namespace") == "sparkle-lore"
                or "sparkle-lore" in str(c.get("source_url") or ""))
        ]

        return lore_chunks

    except Exception as exc:
        print(f"[ip_auditor] lore query error (non-blocking): {exc}")
        return []


# ── Lore validation ────────────────────────────────────────────

async def check_lore(piece: dict) -> tuple[bool, list[str]]:
    """
    Check content against sparkle-lore restrictions.

    Returns (lore_ok: bool, warnings: list[str]).
    lore_ok = False means a restriction chunk was matched.
    """
    theme = piece.get("theme", "")
    voice_script = piece.get("voice_script") or ""
    caption = piece.get("caption") or ""

    query = f"{theme} {voice_script[:200]} {caption[:100]}".strip()
    if not query:
        return True, []

    chunks = await _query_sparkle_lore(query)
    warnings: list[str] = []

    for chunk in chunks:
        # Check for restriction tags in metadata or tags field
        tags = chunk.get("tags") or []
        metadata = chunk.get("chunk_metadata") or {}
        meta_tags = metadata.get("tags") or []
        all_tags = tags + meta_tags

        is_restriction = (
            "restriction" in all_tags
            or metadata.get("type") == "restriction"
            or "restriction" in str(chunk.get("source_type") or "")
        )

        if is_restriction:
            content_preview = (chunk.get("canonical_text") or chunk.get("raw_content") or "")[:120]
            warnings.append(f"Possivel conflito de lore: {content_preview}")

    lore_ok = len(warnings) == 0
    return lore_ok, warnings


# ── Repetition check ───────────────────────────────────────────

async def check_repetition(piece: dict) -> tuple[bool, list[str]]:
    """
    Check if the piece's theme is too similar to recently published content.

    Returns (repetition_ok: bool, warnings: list[str]).
    repetition_ok = False means similar content was published in the last 7 days.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        print("[ip_auditor] rapidfuzz not installed — skipping repetition check")
        return True, []

    theme = piece.get("theme") or ""
    caption = piece.get("caption") or ""
    if not theme and not caption:
        return True, []

    since = (_now() - timedelta(days=7)).isoformat()

    try:
        def _query():
            return (
                supabase.table("content_pieces")
                .select("id, theme, caption, published_at")
                .eq("status", "published")
                .gte("published_at", since)
                .limit(50)
                .execute()
            )
        recent_result = await asyncio.to_thread(_query)
        recent = recent_result.data or []
    except Exception as exc:
        print(f"[ip_auditor] repetition DB query error (non-blocking): {exc}")
        return True, []

    warnings: list[str] = []

    for recent_piece in recent:
        if recent_piece.get("id") == piece.get("id"):
            continue

        recent_theme = recent_piece.get("theme") or ""
        recent_caption = recent_piece.get("caption") or ""

        # Compare themes
        if theme and recent_theme:
            sim = fuzz.ratio(theme.lower(), recent_theme.lower())
            if sim > REPETITION_THRESHOLD:
                warnings.append(
                    f"Tema muito similar a conteudo publicado recentemente "
                    f"({sim}% match com piece {recent_piece.get('id', '')[:8]})"
                )
                continue  # Don't double-warn on same piece

        # Compare captions (first 200 chars as fingerprint)
        if caption and recent_caption:
            cap_a = caption[:200].lower()
            cap_b = recent_caption[:200].lower()
            sim = fuzz.ratio(cap_a, cap_b)
            if sim > REPETITION_THRESHOLD:
                warnings.append(
                    f"Caption muito similar a conteudo publicado recentemente "
                    f"({sim}% match com piece {recent_piece.get('id', '')[:8]})"
                )

    repetition_ok = len(warnings) == 0
    return repetition_ok, warnings


# ── Main auditor ───────────────────────────────────────────────

async def audit_piece(piece: dict) -> dict:
    """
    Run full IP audit on a content_piece.

    - Queries sparkle-lore for lore restrictions
    - Checks for repetition against published pieces
    - Always advances — never blocks

    Writes ip_audit result to pipeline_log.
    Returns audit result dict.
    """
    piece_id = piece["id"]

    # Run both checks in parallel
    lore_task = asyncio.create_task(check_lore(piece))
    rep_task = asyncio.create_task(check_repetition(piece))

    (lore_ok, lore_warnings), (repetition_ok, rep_warnings) = await asyncio.gather(
        lore_task, rep_task
    )

    all_warnings = lore_warnings + rep_warnings

    audit_result = {
        "lore_ok": lore_ok,
        "repetition_ok": repetition_ok,
        "warnings": all_warnings,
        "audited_at": _now_iso(),
    }

    # Persist to pipeline_log
    try:
        current = supabase.table("content_pieces").select("pipeline_log").eq(
            "id", piece_id
        ).limit(1).execute()
        pipeline_log = list(
            (current.data[0].get("pipeline_log") if current.data else None) or []
        )
        pipeline_log.append({
            "event": "ip_audit",
            "ip_audit": audit_result,
            "at": _now_iso(),
        })
        supabase.table("content_pieces").update({
            "pipeline_log": pipeline_log,
            "updated_at": _now_iso(),
        }).eq("id", piece_id).execute()
    except Exception as exc:
        print(f"[ip_auditor] failed to persist audit result (non-blocking): {exc}")

    if all_warnings:
        print(f"[ip_auditor] piece={piece_id[:8]} — {len(all_warnings)} warning(s): {all_warnings[0][:80]}")
    else:
        print(f"[ip_auditor] piece={piece_id[:8]} — clean (lore_ok={lore_ok}, rep_ok={repetition_ok})")

    return audit_result
