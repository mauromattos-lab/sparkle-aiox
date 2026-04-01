"""
Member State Engine — S5-02.

Manages member profiles, EAV state and interaction history.
All members are identified by phone number (E.164 or local format — no normalisation enforced here).

Tables assumed in Supabase (schema defined in migrations/003_member_state_engine.sql):
  - members            — core profile (phone PK-like, name, email, tags jsonb)
  - member_states      — EAV key/value per member
  - member_interactions — rolling interaction log per member

Every function is async-safe via asyncio.to_thread() — the supabase-py client is synchronous.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from runtime.db import supabase


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

async def get_member(phone: str) -> dict[str, Any] | None:
    """
    Fetch a member's full profile including current state (all EAV keys)
    and last 10 interactions.

    Returns None if member does not exist.
    """
    # 1. Core profile
    profile_res = await asyncio.to_thread(
        lambda: supabase
        .table("members")
        .select("*")
        .eq("phone", phone)
        .maybe_single()
        .execute()
    )
    member: dict[str, Any] | None = profile_res.data if profile_res else None
    if not member:
        return None

    # 2. State (all EAV keys for this member)
    state_res = await asyncio.to_thread(
        lambda: supabase
        .table("member_states")
        .select("key, value, set_by, updated_at")
        .eq("phone", phone)
        .execute()
    )
    member["state"] = {
        row["key"]: {
            "value": row["value"],
            "set_by": row["set_by"],
            "updated_at": row["updated_at"],
        }
        for row in (state_res.data or [])
    }

    # 3. Last 10 interactions (chronological)
    interactions_res = await asyncio.to_thread(
        lambda: supabase
        .table("member_interactions")
        .select("id, character_id, channel, summary, sentiment, created_at")
        .eq("phone", phone)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    member["recent_interactions"] = list(
        reversed(interactions_res.data or [])
    )

    return member


async def upsert_member(
    phone: str,
    name: str | None = None,
    email: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create or update a member record.
    On conflict (phone), updates name/email/tags if provided (non-null fields win).
    Returns the upserted member row.
    """
    payload: dict[str, Any] = {"phone": phone, "updated_at": _now_iso()}
    if name is not None:
        payload["name"] = name
    if email is not None:
        payload["email"] = email
    if tags is not None:
        payload["tags"] = tags

    result = await asyncio.to_thread(
        lambda: supabase
        .table("members")
        .upsert(payload, on_conflict="phone")
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else payload


async def set_member_state(
    phone: str,
    key: str,
    value: str,
    set_by: str = "system",
) -> dict[str, Any]:
    """
    Upsert a single EAV key for a member.
    `set_by` identifies who set the value (agent_id, "system", character slug, etc.).
    Returns the upserted state row.
    """
    payload = {
        "phone": phone,
        "key": key,
        "value": value,
        "set_by": set_by,
        "updated_at": _now_iso(),
    }
    result = await asyncio.to_thread(
        lambda: supabase
        .table("member_states")
        .upsert(payload, on_conflict="phone,key")
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else payload


async def add_interaction(
    phone: str,
    character_id: str | None = None,
    channel: str = "whatsapp",
    summary: str = "",
    sentiment: str | None = None,
) -> dict[str, Any]:
    """
    Append an interaction record for a member.
    Used to track which characters/channels the member engaged with and overall sentiment.
    Returns the inserted interaction row.
    """
    payload: dict[str, Any] = {
        "phone": phone,
        "channel": channel,
        "summary": summary,
        "created_at": _now_iso(),
    }
    if character_id is not None:
        payload["character_id"] = character_id
    if sentiment is not None:
        payload["sentiment"] = sentiment

    result = await asyncio.to_thread(
        lambda: supabase
        .table("member_interactions")
        .insert(payload)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else payload


async def get_member_context_for_agent(phone: str) -> str:
    """
    Build a formatted text block ready to be injected into a character's system_prompt.

    Format example:
    ---
    CONTEXTO DO MEMBRO
    Telefone: 5511999999999
    Nome: João Silva
    Tags: [vip, habito-positivo]

    Estado atual:
    - objetivo_saude: perder 10kg (definido por finch)
    - humor_hoje: animado (definido por finch)

    Últimas interações:
    1. [2026-04-01] Finch (whatsapp) — Positivo: Usuário se comprometeu a dormir às 23h.
    2. [2026-04-01] Finch (whatsapp) — Neutro: Perguntas sobre nutrição básica.
    ---

    Returns empty string if member not found.
    """
    member = await get_member(phone)
    if not member:
        return ""

    lines: list[str] = ["--- CONTEXTO DO MEMBRO ---"]

    # Profile
    lines.append(f"Telefone: {member['phone']}")
    if member.get("name"):
        lines.append(f"Nome: {member['name']}")
    if member.get("email"):
        lines.append(f"Email: {member['email']}")
    tags = member.get("tags") or []
    if tags:
        lines.append(f"Tags: [{', '.join(tags)}]")

    # State
    state: dict = member.get("state") or {}
    if state:
        lines.append("\nEstado atual:")
        for key, info in state.items():
            lines.append(f"  - {key}: {info['value']} (definido por {info['set_by']})")
    else:
        lines.append("\n(Sem estado registrado ainda)")

    # Recent interactions
    interactions: list[dict] = member.get("recent_interactions") or []
    if interactions:
        lines.append("\nÚltimas interações:")
        for i, interaction in enumerate(interactions, start=1):
            date_str = (interaction.get("created_at") or "")[:10]
            char = interaction.get("character_id") or "sistema"
            channel = interaction.get("channel") or "?"
            sentiment = interaction.get("sentiment")
            sentiment_str = f" — {sentiment.capitalize()}" if sentiment else ""
            summary = interaction.get("summary") or ""
            lines.append(
                f"  {i}. [{date_str}] {char} ({channel}){sentiment_str}: {summary}"
            )

    lines.append("--- FIM DO CONTEXTO ---")
    return "\n".join(lines)
