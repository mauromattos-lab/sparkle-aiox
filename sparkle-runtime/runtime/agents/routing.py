"""
Agent routing — resolves the best agent for a given intent and context.

Uses agent_type + routing_rules + priority to determine which agent
should handle a request.  Simple DB lookup with priority ordering.

Part of B2-01 Agent Taxonomy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from runtime.db import supabase

logger = logging.getLogger(__name__)


async def resolve_agent(intent: str, context: dict | None = None) -> Optional[dict[str, Any]]:
    """
    Given an intent and context, find the best agent to handle it.

    Resolution strategy (in order):
      1. Look for agents whose routing_rules->intents array contains the intent
      2. If context has a "channel", also filter by routing_rules->channels
      3. Order by priority ASC (lower = higher priority)
      4. Return the first match, or None

    Args:
        intent: The intent string to resolve (e.g. "deploy", "customer_chat").
        context: Optional dict with channel, agent_type filter, etc.

    Returns:
        Full agent dict or None if no match found.
    """
    context = context or {}

    try:
        # Build query: find active agents whose routing_rules contains the intent
        # PostgreSQL: routing_rules->'intents' @> '["intent_value"]'::jsonb
        intent_filter = f'["{intent}"]'

        query = (
            supabase
            .table("agents")
            .select("*")
            .eq("active", True)
            .contains("routing_rules->intents", intent_filter)
        )

        # Optional: filter by agent_type if provided in context
        if context.get("agent_type"):
            query = query.eq("agent_type", context["agent_type"])

        result = await asyncio.to_thread(
            lambda: query.order("priority", desc=False).execute()
        )
    except Exception as exc:
        logger.error("Agent routing failed for intent '%s': %s", intent, exc)
        return None

    rows = result.data or []
    if not rows:
        logger.debug("No agent found for intent '%s'", intent)
        return None

    # If context has a channel, prefer agents that match the channel
    channel = context.get("channel")
    if channel and len(rows) > 1:
        channel_matches = [
            r for r in rows
            if channel in (r.get("routing_rules") or {}).get("channels", [])
        ]
        if channel_matches:
            rows = channel_matches

    agent = rows[0]
    logger.info(
        "Resolved intent '%s' -> agent '%s' (type=%s, priority=%s)",
        intent, agent.get("agent_id"), agent.get("agent_type"), agent.get("priority"),
    )
    return agent


async def list_agents_by_type(agent_type: str) -> list[dict[str, Any]]:
    """
    List all active agents of a given type, ordered by priority.

    Args:
        agent_type: One of 'operational', 'specialist', 'character',
                    'orchestrator', 'observer'.

    Returns:
        List of agent dicts (may be empty).
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase
            .table("agents")
            .select("agent_id, slug, display_name, agent_type, capabilities, priority, routing_rules, status, active")
            .eq("active", True)
            .eq("agent_type", agent_type)
            .order("priority", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to list agents by type '%s': %s", agent_type, exc)
        return []

    return result.data or []


async def get_agent_capabilities(slug: str) -> list[str]:
    """
    Get the capabilities list for an agent by slug.

    Args:
        slug: The agent slug (e.g. "friday", "analyst").

    Returns:
        List of capability strings, or empty list if not found.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase
            .table("agents")
            .select("capabilities")
            .eq("slug", slug)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get capabilities for '%s': %s", slug, exc)
        return []

    row = result.data if result else None
    if not row:
        return []

    return row.get("capabilities") or []


async def get_taxonomy_summary() -> dict[str, Any]:
    """
    Return a summary of the agent taxonomy: count per type, list of types,
    and agents grouped by type.

    Returns:
        {
            "types": ["operational", "specialist", ...],
            "counts": {"operational": 3, "specialist": 7, ...},
            "agents_by_type": {
                "operational": [{"agent_id": "friday", ...}, ...],
                ...
            },
            "total": 13
        }
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase
            .table("agents")
            .select("agent_id, display_name, agent_type, capabilities, priority, status")
            .eq("active", True)
            .order("priority", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get taxonomy summary: %s", exc)
        return {"types": [], "counts": {}, "agents_by_type": {}, "total": 0}

    rows = result.data or []

    # Group by type
    agents_by_type: dict[str, list[dict]] = {}
    for row in rows:
        atype = row.get("agent_type", "unknown")
        if atype not in agents_by_type:
            agents_by_type[atype] = []
        agents_by_type[atype].append(row)

    types = sorted(agents_by_type.keys())
    counts = {t: len(agents) for t, agents in agents_by_type.items()}

    return {
        "types": types,
        "counts": counts,
        "agents_by_type": agents_by_type,
        "total": len(rows),
    }
