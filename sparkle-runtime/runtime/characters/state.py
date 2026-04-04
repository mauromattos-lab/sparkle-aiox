"""
Character state — B1-02.

Canonical state for each character IP (mood, energy, arc, personality).
Source of truth: Supabase `character_state` table.
In-memory cache with 60s TTL to reduce DB hits.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from runtime.db import supabase

# ── In-memory cache (slug -> (data, fetched_at)) ─────────────────────────
_cache: dict[str, tuple[dict[str, Any], float]] = {}
_CACHE_TTL = 60  # seconds


def _cache_get(slug: str) -> dict[str, Any] | None:
    """Return cached state if still fresh, else None."""
    entry = _cache.get(slug)
    if entry is None:
        return None
    data, fetched_at = entry
    if time.monotonic() - fetched_at > _CACHE_TTL:
        del _cache[slug]
        return None
    return data


def _cache_set(slug: str, data: dict[str, Any]) -> None:
    _cache[slug] = (data, time.monotonic())


def _cache_invalidate(slug: str) -> None:
    _cache.pop(slug, None)


# ── Public API ────────────────────────────────────────────────────────────

async def get_character_state(slug: str) -> dict[str, Any]:
    """
    Fetch current character state from cache or Supabase.

    If the character has no row yet, creates one with defaults and returns it.
    """
    cached = _cache_get(slug)
    if cached is not None:
        return cached

    result = await asyncio.to_thread(
        lambda: supabase.table("character_state")
        .select("*")
        .eq("character_slug", slug)
        .maybe_single()
        .execute()
    )

    data: dict[str, Any] | None = result.data if result else None

    if data is None:
        # Auto-create with defaults
        insert_result = await asyncio.to_thread(
            lambda: supabase.table("character_state")
            .insert({"character_slug": slug})
            .execute()
        )
        data = insert_result.data[0] if insert_result.data else {"character_slug": slug}

    _cache_set(slug, data)
    return data


async def update_character_state(slug: str, updates: dict[str, Any]) -> dict[str, Any]:
    """
    Partial update of character state fields.

    Allowed fields: mood, energy, arc_position, personality_traits, session_context.
    Automatically sets updated_at.
    """
    allowed = {"mood", "energy", "arc_position", "personality_traits", "session_context"}
    filtered = {k: v for k, v in updates.items() if k in allowed}

    if not filtered:
        return await get_character_state(slug)

    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await asyncio.to_thread(
        lambda: supabase.table("character_state")
        .update(filtered)
        .eq("character_slug", slug)
        .execute()
    )

    data = result.data[0] if result.data else None

    if data is None:
        # Row didn't exist — create then update
        await get_character_state(slug)  # ensures row exists
        result = await asyncio.to_thread(
            lambda: supabase.table("character_state")
            .update(filtered)
            .eq("character_slug", slug)
            .execute()
        )
        data = result.data[0] if result.data else await get_character_state(slug)

    _cache_invalidate(slug)
    _cache_set(slug, data)
    return data


async def record_character_event(
    slug: str,
    event: str,
    mood_effect: str | None = None,
    energy_delta: float = 0.0,
) -> dict[str, Any]:
    """
    Record an event for a character, optionally changing mood and energy.

    - event: description of what happened (e.g. "completed_quest", "received_feedback")
    - mood_effect: if provided, sets the new mood (e.g. "excited", "melancholic")
    - energy_delta: added to current energy, clamped to [0.00, 0.99]
    """
    now = datetime.now(timezone.utc).isoformat()

    # Ensure row exists first
    current = await get_character_state(slug)

    patch: dict[str, Any] = {
        "last_event": event,
        "last_event_at": now,
        "updated_at": now,
    }

    if mood_effect is not None:
        patch["mood"] = mood_effect

    if energy_delta != 0.0:
        current_energy = float(current.get("energy", 0.75))
        new_energy = max(0.0, min(0.99, current_energy + energy_delta))
        patch["energy"] = round(new_energy, 2)

    result = await asyncio.to_thread(
        lambda: supabase.table("character_state")
        .update(patch)
        .eq("character_slug", slug)
        .execute()
    )

    data = result.data[0] if result.data else current
    _cache_invalidate(slug)
    _cache_set(slug, data)
    return data
