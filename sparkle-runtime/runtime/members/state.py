"""
Member State Engine — B4-05 Community Gamification Layer.

Manages community member state with XP, levels, engagement scores,
and event tracking. Scoped by client_id for multi-tenant communities.

Tables (defined in migrations/010_member_state.sql):
  - member_state   — XP, level, engagement per community member
  - member_events  — event log with XP attribution

Every function is async-safe via asyncio.to_thread().
"""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any

from runtime.db import supabase


# ── Internal helpers ─────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Level Calculation ────────────────────────────────────────────────────────

# 10 levels with increasing XP thresholds.
# Level 1: 0 XP, Level 2: 100 XP, Level 3: 250 XP, ...
# Formula: threshold(n) = round(100 * (n-1)^1.5) for n >= 2
LEVEL_THRESHOLDS: list[int] = [0]  # Level 1 starts at 0
for _n in range(2, 11):
    LEVEL_THRESHOLDS.append(round(100 * (_n - 1) ** 1.5))
# Result: [0, 100, 283, 520, 800, 1118, 1470, 1852, 2263, 2700]


def calculate_level(xp: int) -> int:
    """
    Convert XP to level (1-10).

    Thresholds increase with a power curve so early levels are quick
    but higher levels require sustained engagement.
    """
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp >= threshold:
            level = i + 1
        else:
            break
    return min(level, 10)


# ── Public API ───────────────────────────────────────────────────────────────

async def get_member(client_id: str, member_id: str) -> dict[str, Any] | None:
    """
    Fetch a community member's state by client_id + member_id.

    Returns None if the member does not exist.
    """
    result = await asyncio.to_thread(
        lambda: supabase
        .table("member_state")
        .select("*")
        .eq("client_id", client_id)
        .eq("member_id", member_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


async def list_members(
    client_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    List members for a client, optionally filtered by status.
    """
    def _query():
        q = (
            supabase
            .table("member_state")
            .select("*")
            .eq("client_id", client_id)
        )
        if status:
            q = q.eq("status", status)
        return q.order("xp", desc=True).limit(limit).execute()

    result = await asyncio.to_thread(_query)
    return result.data or []


async def create_member(
    client_id: str,
    member_id: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    """
    Create a new community member. Returns the created row.

    If a member with the same client_id + member_id already exists,
    the upsert updates display_name (if provided) and refreshes updated_at.
    """
    now = _now_iso()
    payload: dict[str, Any] = {
        "client_id": client_id,
        "member_id": member_id,
        "joined_at": now,
        "last_active_at": now,
        "created_at": now,
        "updated_at": now,
    }
    if display_name is not None:
        payload["display_name"] = display_name

    result = await asyncio.to_thread(
        lambda: supabase
        .table("member_state")
        .upsert(payload, on_conflict="client_id,member_id")
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else payload


async def update_member(
    member_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Partial update of a community member by their UUID (id column).

    Allowed fields: display_name, status, engagement_score, metadata,
    last_active_at.
    """
    allowed = {
        "display_name", "status", "engagement_score",
        "metadata", "last_active_at",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return None

    filtered["updated_at"] = _now_iso()

    result = await asyncio.to_thread(
        lambda: supabase
        .table("member_state")
        .update(filtered)
        .eq("id", member_id)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


async def record_event(
    member_id: str,
    event_type: str,
    event_data: dict[str, Any] | None = None,
    xp_earned: int = 0,
) -> dict[str, Any]:
    """
    Record an event for a community member (by UUID) and update their XP/level.

    Steps:
    1. Insert event into member_events
    2. If xp_earned > 0, update member_state XP and recalculate level
    3. Update last_active_at

    Returns the inserted event row augmented with new_xp and new_level.
    """
    now = _now_iso()

    # 1. Insert event
    event_payload: dict[str, Any] = {
        "member_id": member_id,
        "event_type": event_type,
        "event_data": event_data or {},
        "xp_earned": xp_earned,
        "created_at": now,
    }
    event_result = await asyncio.to_thread(
        lambda: supabase
        .table("member_events")
        .insert(event_payload)
        .execute()
    )
    event_row = (event_result.data or [{}])[0]

    # 2. Update XP + level + last_active_at on member_state
    if xp_earned > 0:
        # Fetch current XP
        current = await asyncio.to_thread(
            lambda: supabase
            .table("member_state")
            .select("xp")
            .eq("id", member_id)
            .maybe_single()
            .execute()
        )
        current_xp = (current.data or {}).get("xp", 0) if current else 0
        new_xp = current_xp + xp_earned
        new_level = calculate_level(new_xp)

        await asyncio.to_thread(
            lambda: supabase
            .table("member_state")
            .update({
                "xp": new_xp,
                "level": new_level,
                "last_active_at": now,
                "updated_at": now,
            })
            .eq("id", member_id)
            .execute()
        )
        event_row["new_xp"] = new_xp
        event_row["new_level"] = new_level
    else:
        # Still update last_active_at
        await asyncio.to_thread(
            lambda: supabase
            .table("member_state")
            .update({
                "last_active_at": now,
                "updated_at": now,
            })
            .eq("id", member_id)
            .execute()
        )

    return event_row


async def get_leaderboard(
    client_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Return top members for a client community, ranked by XP descending.

    Only active members are included.
    """
    result = await asyncio.to_thread(
        lambda: supabase
        .table("member_state")
        .select("id, member_id, display_name, level, xp, engagement_score, last_active_at")
        .eq("client_id", client_id)
        .eq("status", "active")
        .order("xp", desc=True)
        .limit(limit)
        .execute()
    )
    rows = result.data or []
    # Add rank
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows
