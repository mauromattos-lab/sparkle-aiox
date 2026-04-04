"""
Agent loader — fetches agent config from Supabase `agents` table.

Used by activate_agent handler and other components that need agent
configuration.  Falls back to hardcoded dict if DB lookup fails.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from runtime.db import supabase

logger = logging.getLogger(__name__)


async def load_agent(slug: str) -> Optional[dict[str, Any]]:
    """
    Load an agent by slug from Supabase.

    Returns a dict compatible with _AVAILABLE_AGENTS format:
        {
            "name": "@analyst",
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "max_tool_iterations": 10,
            "timeout_s": 90,
            "system_prompt": "...",
            "skills": [...],
            "tools": [...],
            "config": {...},
            "agent_type": "specialist",
            "character_id": None,
        }

    Returns None if not found or inactive.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase
            .table("agents")
            .select("*")
            .eq("slug", slug)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to load agent '%s' from DB: %s", slug, exc)
        return None

    row: dict[str, Any] | None = result.data if result else None
    if not row:
        return None

    # Extract config overrides (max_tool_iterations, timeout_s)
    config = row.get("config") or {}

    # Parse tools from jsonb (list of strings)
    tools_raw = row.get("tools") or []
    if isinstance(tools_raw, str):
        import json
        try:
            tools_raw = json.loads(tools_raw)
        except Exception:
            tools_raw = []

    return {
        "name": row.get("display_name") or f"@{slug}",
        "model": row.get("model") or "claude-sonnet-4-6",
        "max_tokens": row.get("max_tokens") or 4096,
        "max_tool_iterations": config.get("max_tool_iterations", 10),
        "timeout_s": config.get("timeout_s", 90),
        "system_prompt": row.get("system_prompt") or "",
        "skills": row.get("skills") or [],
        "tools": tools_raw,
        "config": config,
        "agent_type": row.get("agent_type") or "specialist",
        "character_id": row.get("character_id"),
        "slug": slug,
    }


async def list_active_agents() -> list[dict[str, Any]]:
    """
    List all active agents from Supabase.

    Returns a list of dicts with key fields for each agent.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase
            .table("agents")
            .select("slug, display_name, agent_type, model, max_tokens, skills, config, active, character_id, created_at, updated_at")
            .eq("active", True)
            .order("slug")
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to list agents from DB: %s", exc)
        return []

    return result.data or []
