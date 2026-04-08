"""
IP Auditor — W1-CHAR-1 (upgraded from CONTENT-1.10).

Validates content_pieces against Zenya's lore (Brain namespace 'sparkle-lore'
and table character_lore) and checks for repetition against recently published
pieces.

Rules:
  - Always advances — NEVER blocks the pipeline
  - Warnings are written to pipeline_log under 'ip_audit' key
  - Lore check: queries Brain via match_lore_chunks RPC (namespace-precise)
    + character_lore table (structural lore: personality, backstory, arc)
  - Semantic compliance: Claude Haiku verifies positive lore compatibility
    (COMPATIVEL / INCOMPATIVEL) — not just restriction tags
  - Repetition check: fuzzy-match against pieces published in last 7 days

Called by pipeline.py between video_done and pending_approval.

Changes in W1-CHAR-1:
  - _query_sparkle_lore(): uses match_lore_chunks RPC with namespace='sparkle-lore'
    as primary filter — no more fragile Python post-filter (AC-1)
  - _query_character_lore(): new — queries character_lore for Zenya's structured
    lore entries (personality, backstory, arc) (AC-3)
  - _check_lore_compliance(): new — Claude Haiku semantic verification (AC-2)
  - audit_result now includes: lore_compliance, lore_compliance_reason,
    lore_chunks_used, character_lore_entries_used (AC-4)
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase

# Fuzzy match threshold for repetition detection (0-100)
REPETITION_THRESHOLD = 80

# Zenya character UUID (from characters table WHERE slug='zenya')
ZENYA_CHARACTER_ID = "105d29c4-dbc5-4cf4-9fba-16f36f167c78"

# character_lore types relevant for content compliance checking
LORE_COMPLIANCE_TYPES = ("personality", "backstory", "arc", "archetype", "voice", "philosophy")

# Claude Haiku model for semantic compliance check
HAIKU_MODEL = "claude-haiku-4-5"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ── Brain query (AC-1) ─────────────────────────────────────────

async def _query_sparkle_lore(query_text: str, top_k: int = 5) -> list[dict]:
    """
    Query Brain namespace 'sparkle-lore' using match_lore_chunks RPC.

    Uses the match_lore_chunks Postgres function which filters directly by
    namespace='sparkle-lore' and curation_status='approved' — no Python
    post-filter required.

    Returns list of chunk dicts with keys: id, namespace, canonical_text,
    chunk_metadata, similarity.
    Gracefully returns [] on any error — auditor never blocks.
    """
    try:
        from runtime.brain.embedding import get_embedding

        embedding = await get_embedding(query_text)
        if not embedding:
            print("[ip_auditor] embedding unavailable — skipping lore check")
            return []

        # Use match_lore_chunks RPC — filters by namespace as primary parameter
        result = await asyncio.to_thread(
            lambda: supabase.rpc(
                "match_lore_chunks",
                {
                    "query_embedding": embedding,
                    "namespace_in": "sparkle-lore",
                    "match_count": top_k,
                },
            ).execute()
        )

        return result.data or []

    except Exception as exc:
        print(f"[ip_auditor] lore query error (non-blocking): {exc}")
        return []


# ── character_lore query (AC-3) ────────────────────────────────

async def _query_character_lore(
    lore_types: tuple[str, ...] = LORE_COMPLIANCE_TYPES,
    max_entries: int = 8,
) -> list[str]:
    """
    Query character_lore for Zenya's structural lore entries.

    Filters by character_id=ZENYA_CHARACTER_ID, is_public=True, and
    lore_type IN (personality, backstory, arc, archetype, voice, philosophy).

    Returns list of formatted strings ready to be included in the Haiku prompt.
    Gracefully returns [] on any error — auditor never blocks (AC-5).
    """
    try:
        now_iso = _now_iso()

        def _fetch():
            return (
                supabase.table("character_lore")
                .select("lore_type, title, content")
                .eq("character_id", ZENYA_CHARACTER_ID)
                .eq("is_public", True)
                .in_("lore_type", list(lore_types))
                .or_(f"reveal_after.is.null,reveal_after.lte.{now_iso}")
                .order("created_at", desc=False)
                .limit(max_entries)
                .execute()
            )

        result = await asyncio.to_thread(_fetch)
        items = result.data or []

        if not items:
            print("[ip_auditor] character_lore returned empty — continuing with Brain lore only")
            return []

        entries = []
        for item in items:
            lore_type = item.get("lore_type", "lore")
            title = item.get("title", "")
            content = item.get("content", "")
            entries.append(f"[{lore_type}] {title}: {content[:300]}")

        return entries

    except Exception as exc:
        print(f"[ip_auditor] character_lore query error (non-blocking): {exc}")
        return []


# ── Haiku semantic compliance (AC-2) ───────────────────────────

async def _check_lore_compliance(
    piece: dict,
    lore_chunks: list[dict],
    character_lore_entries: list[str],
) -> tuple[str, str]:
    """
    Ask Claude Haiku whether the piece content is compatible with Zenya's lore.

    Returns (compliance: str, reason: str) where compliance is one of:
      'COMPATIVEL'   — content is consistent with lore
      'INCOMPATIVEL' — content contradicts lore (adds warning but never blocks)
      'SKIPPED'      — Haiku call failed or timed out

    Haiku is called with a 10s timeout. On any error, returns ('SKIPPED', '').
    """
    if not lore_chunks and not character_lore_entries:
        return "SKIPPED", "sem lore disponivel para verificacao"

    try:
        import anthropic

        theme = piece.get("theme", "")
        voice_script = piece.get("voice_script") or ""
        caption = piece.get("caption") or ""
        content_text = f"Tema: {theme}\nScript: {voice_script[:400]}\nCaption: {caption[:200]}"

        # Build lore context from Brain chunks (top 3)
        lore_context_parts: list[str] = []
        for chunk in lore_chunks[:3]:
            text = chunk.get("canonical_text") or ""
            if text:
                lore_context_parts.append(text[:300])

        # Add character_lore entries
        lore_context_parts.extend(character_lore_entries[:5])

        lore_context = "\n---\n".join(lore_context_parts)

        prompt = (
            "Você é um auditor de consistência de personagem para a Zenya, personagem de IA da Sparkle.\n\n"
            f"LORE CANÔNICO DA ZENYA:\n{lore_context}\n\n"
            f"CONTEÚDO GERADO:\n{content_text}\n\n"
            "O conteúdo acima é consistente com o lore da Zenya descrito? "
            "Responda COMPATIVEL ou INCOMPATIVEL com justificativa em até 20 palavras."
        )

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

        def _call_haiku():
            return client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
                timeout=10,
            )

        response = await asyncio.wait_for(
            asyncio.to_thread(_call_haiku),
            timeout=12,
        )

        raw = (response.content[0].text or "").strip()

        # Parse COMPATIVEL / INCOMPATIVEL
        upper = raw.upper()
        if "INCOMPATIVEL" in upper:
            compliance = "INCOMPATIVEL"
            # Extract justification after the keyword
            idx = upper.find("INCOMPATIVEL")
            reason_raw = raw[idx + len("INCOMPATIVEL"):].strip(" :—-\n")
            reason = reason_raw[:100] if reason_raw else raw[:100]
        elif "COMPATIVEL" in upper:
            compliance = "COMPATIVEL"
            idx = upper.find("COMPATIVEL")
            reason_raw = raw[idx + len("COMPATIVEL"):].strip(" :—-\n")
            reason = reason_raw[:100] if reason_raw else ""
        else:
            # Haiku returned something unexpected — treat as SKIPPED
            compliance = "SKIPPED"
            reason = raw[:100]

        return compliance, reason

    except asyncio.TimeoutError:
        print("[ip_auditor] Haiku timeout — lore_compliance=SKIPPED")
        return "SKIPPED", "timeout"
    except Exception as exc:
        print(f"[ip_auditor] Haiku error (non-blocking): {exc}")
        return "SKIPPED", str(exc)[:80]


# ── Lore validation (AC-1 + AC-2 + AC-3) ──────────────────────

async def check_lore(piece: dict) -> tuple[bool, list[str], dict]:
    """
    Check content against sparkle-lore and character_lore.

    Runs:
      1. Brain query via match_lore_chunks RPC (namespace='sparkle-lore')
      2. character_lore query for Zenya structural lore
      3. Claude Haiku semantic compatibility check

    Returns (lore_ok: bool, warnings: list[str], extras: dict).
    lore_ok = False means a restriction chunk was matched.
    extras contains: lore_compliance, lore_compliance_reason,
                     lore_chunks_used, character_lore_entries_used.
    """
    theme = piece.get("theme", "")
    voice_script = piece.get("voice_script") or ""
    caption = piece.get("caption") or ""

    query = f"{theme} {voice_script[:200]} {caption[:100]}".strip()
    if not query:
        return True, [], {
            "lore_compliance": "SKIPPED",
            "lore_compliance_reason": "sem conteudo para auditar",
            "lore_chunks_used": 0,
            "character_lore_entries_used": 0,
        }

    # Run Brain query + character_lore query in parallel
    chunks_task = asyncio.create_task(_query_sparkle_lore(query, top_k=5))
    char_lore_task = asyncio.create_task(_query_character_lore())
    lore_chunks, character_lore_entries = await asyncio.gather(chunks_task, char_lore_task)

    warnings: list[str] = []

    # Legacy restriction-tag check (kept for backward compat)
    for chunk in lore_chunks:
        metadata = chunk.get("chunk_metadata") or {}
        meta_tags = metadata.get("tags") or []

        is_restriction = (
            "restriction" in meta_tags
            or metadata.get("type") == "restriction"
            or metadata.get("lore_type") == "restriction"
        )

        if is_restriction:
            content_preview = (chunk.get("canonical_text") or "")[:120]
            warnings.append(f"Possivel conflito de lore (restriction): {content_preview}")

    lore_ok = len(warnings) == 0

    # Semantic compliance via Haiku (AC-2)
    compliance, reason = await _check_lore_compliance(
        piece, lore_chunks, character_lore_entries
    )

    if compliance == "INCOMPATIVEL":
        warnings.append(f"Lore incompativel com lore canonico da Zenya: {reason}")

    extras = {
        "lore_compliance": compliance,
        "lore_compliance_reason": reason if reason else None,
        "lore_chunks_used": len(lore_chunks),
        "character_lore_entries_used": len(character_lore_entries),
    }

    return lore_ok, warnings, extras


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


# ── Main auditor (AC-4 + AC-5) ────────────────────────────────

async def audit_piece(piece: dict) -> dict:
    """
    Run full IP audit on a content_piece.

    - Queries sparkle-lore (Brain, namespace='sparkle-lore') via match_lore_chunks RPC
    - Queries character_lore for Zenya's structural lore entries
    - Runs Claude Haiku semantic compliance check
    - Checks for repetition against published pieces
    - Always advances — never blocks (AC-5)

    audit_result structure (AC-4):
    {
        "lore_ok": bool,
        "lore_compliance": "COMPATIVEL" | "INCOMPATIVEL" | "SKIPPED",
        "lore_compliance_reason": str | null,
        "lore_chunks_used": int,
        "character_lore_entries_used": int,
        "repetition_ok": bool,
        "warnings": list[str],
        "audited_at": ISO str,
    }

    Writes ip_audit result to pipeline_log.
    Returns audit result dict.
    """
    piece_id = piece["id"]

    # Run lore check + repetition check in parallel
    lore_task = asyncio.create_task(check_lore(piece))
    rep_task = asyncio.create_task(check_repetition(piece))

    (lore_ok, lore_warnings, lore_extras), (repetition_ok, rep_warnings) = (
        await asyncio.gather(lore_task, rep_task)
    )

    all_warnings = lore_warnings + rep_warnings

    audit_result = {
        "lore_ok": lore_ok,
        "lore_compliance": lore_extras.get("lore_compliance", "SKIPPED"),
        "lore_compliance_reason": lore_extras.get("lore_compliance_reason"),
        "lore_chunks_used": lore_extras.get("lore_chunks_used", 0),
        "character_lore_entries_used": lore_extras.get("character_lore_entries_used", 0),
        "repetition_ok": repetition_ok,
        "warnings": all_warnings,
        "audited_at": _now_iso(),
    }

    # Persist to pipeline_log (non-blocking)
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

    compliance = audit_result["lore_compliance"]
    if all_warnings:
        print(
            f"[ip_auditor] piece={piece_id[:8]} — {len(all_warnings)} warning(s), "
            f"compliance={compliance}: {all_warnings[0][:80]}"
        )
    else:
        print(
            f"[ip_auditor] piece={piece_id[:8]} — clean "
            f"(lore_ok={lore_ok}, compliance={compliance}, rep_ok={repetition_ok}, "
            f"chunks={audit_result['lore_chunks_used']}, "
            f"char_lore={audit_result['character_lore_entries_used']})"
        )

    return audit_result
