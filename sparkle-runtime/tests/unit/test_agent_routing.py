"""
Unit tests for Agent Routing (B2-01).

Tests resolve_agent intent matching, priority-based selection,
channel filtering, list_agents_by_type, get_agent_capabilities,
and get_taxonomy_summary.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_agent(agent_id, agent_type="specialist", priority=10, intents=None, channels=None, capabilities=None):
    """Build a mock agent row."""
    return {
        "agent_id": agent_id,
        "slug": agent_id,
        "display_name": agent_id.capitalize(),
        "agent_type": agent_type,
        "priority": priority,
        "capabilities": capabilities or [],
        "routing_rules": {
            "intents": intents or [],
            "channels": channels or [],
        },
        "status": "active",
        "active": True,
    }


def _mock_supabase_query(rows):
    """Create a mock supabase query chain that returns the given rows."""
    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.select.return_value = mock_q
    mock_q.eq.return_value = mock_q
    mock_q.contains.return_value = mock_q
    mock_q.order.return_value = mock_q
    mock_q.maybe_single.return_value = mock_q
    mock_q.execute.return_value = MagicMock(data=rows)
    mock_sb.table.return_value = mock_q
    return mock_sb


# ── resolve_agent tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_agent_simple_match():
    from runtime.agents.routing import resolve_agent

    agents = [_mock_agent("analyst", intents=["market_research"], priority=5)]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("market_research")

    assert result is not None
    assert result["agent_id"] == "analyst"


@pytest.mark.asyncio
async def test_resolve_agent_no_match():
    from runtime.agents.routing import resolve_agent

    mock_sb = _mock_supabase_query([])

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("nonexistent_intent")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_agent_priority_ordering():
    """Lower priority number = higher priority. First match should win."""
    from runtime.agents.routing import resolve_agent

    agents = [
        _mock_agent("dev", intents=["deploy"], priority=5),
        _mock_agent("devops", intents=["deploy"], priority=10),
    ]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("deploy")

    assert result["agent_id"] == "dev"  # lower priority number wins


@pytest.mark.asyncio
async def test_resolve_agent_channel_filter():
    """When context has a channel, prefer agents that match that channel."""
    from runtime.agents.routing import resolve_agent

    agents = [
        _mock_agent("friday", intents=["chat"], priority=5, channels=["whatsapp"]),
        _mock_agent("portal_agent", intents=["chat"], priority=5, channels=["portal"]),
    ]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("chat", context={"channel": "portal"})

    assert result["agent_id"] == "portal_agent"


@pytest.mark.asyncio
async def test_resolve_agent_channel_no_match_keeps_all():
    """If no agent matches the channel, return the first by priority."""
    from runtime.agents.routing import resolve_agent

    agents = [
        _mock_agent("friday", intents=["chat"], priority=5, channels=["whatsapp"]),
    ]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("chat", context={"channel": "telegram"})

    assert result["agent_id"] == "friday"  # still returns first match


@pytest.mark.asyncio
async def test_resolve_agent_db_error():
    from runtime.agents.routing import resolve_agent

    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("DB down")

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("chat")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_agent_with_agent_type_filter():
    """Context with agent_type should filter by that type."""
    from runtime.agents.routing import resolve_agent

    agents = [_mock_agent("friday", agent_type="operational", intents=["chat"])]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await resolve_agent("chat", context={"agent_type": "operational"})

    assert result is not None


# ── list_agents_by_type tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_by_type():
    from runtime.agents.routing import list_agents_by_type

    agents = [
        _mock_agent("friday", agent_type="operational", priority=1),
        _mock_agent("worker", agent_type="operational", priority=2),
    ]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await list_agents_by_type("operational")

    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_agents_empty():
    from runtime.agents.routing import list_agents_by_type

    mock_sb = _mock_supabase_query([])

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await list_agents_by_type("nonexistent_type")

    assert result == []


@pytest.mark.asyncio
async def test_list_agents_db_error():
    from runtime.agents.routing import list_agents_by_type

    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("DB down")

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await list_agents_by_type("operational")

    assert result == []


# ── get_agent_capabilities tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_capabilities_found():
    from runtime.agents.routing import get_agent_capabilities

    mock_sb = _mock_supabase_query({"capabilities": ["chat", "deploy", "brain_query"]})

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_agent_capabilities("friday")

    assert "chat" in result
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_capabilities_not_found():
    from runtime.agents.routing import get_agent_capabilities

    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.select.return_value = mock_q
    mock_q.eq.return_value = mock_q
    mock_q.maybe_single.return_value = mock_q
    mock_q.execute.return_value = MagicMock(data=None)
    mock_sb.table.return_value = mock_q

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_agent_capabilities("nonexistent")

    assert result == []


@pytest.mark.asyncio
async def test_get_capabilities_db_error():
    from runtime.agents.routing import get_agent_capabilities

    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("DB down")

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_agent_capabilities("friday")

    assert result == []


@pytest.mark.asyncio
async def test_get_capabilities_null_capabilities():
    from runtime.agents.routing import get_agent_capabilities

    mock_sb = _mock_supabase_query({"capabilities": None})

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_agent_capabilities("friday")

    assert result == []


# ── get_taxonomy_summary tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_taxonomy_summary():
    from runtime.agents.routing import get_taxonomy_summary

    agents = [
        _mock_agent("friday", agent_type="operational", priority=1),
        _mock_agent("worker", agent_type="operational", priority=2),
        _mock_agent("analyst", agent_type="specialist", priority=5),
        _mock_agent("zenya", agent_type="character", priority=10),
    ]
    mock_sb = _mock_supabase_query(agents)

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_taxonomy_summary()

    assert result["total"] == 4
    assert "operational" in result["types"]
    assert "specialist" in result["types"]
    assert "character" in result["types"]
    assert result["counts"]["operational"] == 2
    assert result["counts"]["specialist"] == 1


@pytest.mark.asyncio
async def test_taxonomy_summary_empty():
    from runtime.agents.routing import get_taxonomy_summary

    mock_sb = _mock_supabase_query([])

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_taxonomy_summary()

    assert result["total"] == 0
    assert result["types"] == []
    assert result["counts"] == {}


@pytest.mark.asyncio
async def test_taxonomy_summary_db_error():
    from runtime.agents.routing import get_taxonomy_summary

    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("DB down")

    with patch("runtime.agents.routing.supabase", mock_sb):
        result = await get_taxonomy_summary()

    assert result["total"] == 0
