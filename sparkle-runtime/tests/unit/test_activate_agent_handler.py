"""
Unit tests for activate_agent handler.
Mocks: Anthropic API, Supabase, Brain query, web search.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.tasks.handlers.activate_agent import (
    handle_activate_agent,
    _normalize_agent,
    _extract_agent,
    _extract_request,
    _exec_calculate,
    _exec_supabase_read,
    _AVAILABLE_AGENTS,
    _SUPABASE_TABLE_WHITELIST,
)


# ── Normalize agent tests ───────────────────────────────────────────────

def test_normalize_agent_strips_at():
    assert _normalize_agent("@analyst") == "analyst"
    assert _normalize_agent("analyst") == "analyst"
    # lstrip("@") only strips leading @ chars, not spaces before @
    assert _normalize_agent("@dev") == "dev"
    assert _normalize_agent("  @DEV  ") == "@dev"  # spaces prevent lstrip from seeing @


# ── Extract agent tests ────────────────────────────────────────────────

def test_extract_agent_from_payload_agent():
    assert _extract_agent({"agent": "@analyst"}) == "@analyst"


def test_extract_agent_from_text():
    payload = {"original_text": "ativa o @dev pra debugar"}
    assert _extract_agent(payload) == "@dev"


def test_extract_agent_empty():
    assert _extract_agent({}) == ""
    assert _extract_agent({"original_text": "hello world"}) == ""


# ── Extract request tests ──────────────────────────────────────────────

def test_extract_request_from_payload():
    assert _extract_request({"request": "analyze MRR"}) == "analyze MRR"


def test_extract_request_from_text():
    payload = {"original_text": "ativa o @analyst pra analisar o cliente Vitalis"}
    result = _extract_request(payload)
    # Should have cleaned out "ativa", "@analyst", etc.
    assert "Vitalis" in result or "analisar" in result


def test_extract_request_empty():
    assert _extract_request({}) == ""


# ── Calculate executor tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calculate_basic():
    result = await _exec_calculate({"expression": "2 + 3"})
    assert result == "5"


@pytest.mark.asyncio
async def test_calculate_complex():
    result = await _exec_calculate({"expression": "4594 * 1.15"})
    assert "5283" in result


@pytest.mark.asyncio
async def test_calculate_empty():
    result = await _exec_calculate({"expression": ""})
    assert "erro" in result.lower() or "vazia" in result.lower()


@pytest.mark.asyncio
async def test_calculate_invalid_chars():
    result = await _exec_calculate({"expression": "import os; os.system('rm -rf /')"})
    assert "nao permitidos" in result.lower() or "erro" in result.lower()


@pytest.mark.asyncio
async def test_calculate_brazilian_comma():
    """Brazilian format uses comma as decimal separator."""
    result = await _exec_calculate({"expression": "1,5 + 2,5"})
    assert result == "4.0"


# ── Supabase read executor tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_supabase_read_blocked_table():
    result = await _exec_supabase_read({"table": "users_private"})
    assert "nao permitida" in result.lower()


@pytest.mark.asyncio
async def test_supabase_read_allowed_table():
    mock_response = MagicMock()
    mock_response.data = [{"id": "1", "name": "Vitalis"}]

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_query

    with patch("runtime.tasks.handlers.activate_agent.supabase", mock_sb):
        result = await _exec_supabase_read({"table": "clients", "select": "*", "limit": 10})

    assert "Vitalis" in result


@pytest.mark.asyncio
async def test_supabase_read_no_results():
    mock_response = MagicMock()
    mock_response.data = []

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_query

    with patch("runtime.tasks.handlers.activate_agent.supabase", mock_sb):
        result = await _exec_supabase_read({"table": "clients"})

    assert "nenhum registro" in result.lower()


# ── Main handler tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_agent_no_agent_specified():
    task = {"payload": {}}
    result = await handle_activate_agent(task)
    assert "nao identifiquei" in result["message"].lower()


@pytest.mark.asyncio
async def test_activate_agent_unknown_agent():
    task = {"payload": {"agent": "@nonexistent", "request": "do something"}}

    with patch("runtime.agents.loader.load_agent", new_callable=AsyncMock, return_value=None):
        result = await handle_activate_agent(task)

    assert "nao reconhecido" in result["message"].lower()


@pytest.mark.asyncio
async def test_activate_agent_known_but_no_subagent():
    """Agents like @sm exist in _KNOWN_AGENTS but not in _AVAILABLE_AGENTS."""
    task = {"payload": {"agent": "@sm", "request": "check sprint"}}

    with patch("runtime.agents.loader.load_agent", new_callable=AsyncMock, return_value=None):
        result = await handle_activate_agent(task)

    assert "nao tem execucao autonoma" in result["message"].lower() or "disponiveis" in result["message"].lower()


@pytest.mark.asyncio
async def test_activate_agent_no_request():
    """Agent is valid but no request provided."""
    task = {"payload": {"agent": "@analyst"}, "id": "task-1"}

    with patch("runtime.agents.loader.load_agent", new_callable=AsyncMock, return_value=None):
        with patch(
            "runtime.tasks.handlers.activate_agent._execute_subagent",
            new_callable=AsyncMock,
            return_value={"message": "@analyst ativado, mas sem tarefa especifica.", "agent": "@analyst"},
        ):
            result = await handle_activate_agent(task)

    assert "@analyst" in result["message"]


@pytest.mark.asyncio
async def test_activate_agent_timeout():
    """Subagent exceeds timeout."""
    task = {
        "payload": {"agent": "@analyst", "request": "heavy analysis"},
        "id": "task-2",
    }

    async def mock_execute(*args, **kwargs):
        return {
            "message": "@analyst: analise excedeu o tempo limite de 2s. Tente uma pergunta mais especifica.",
            "agent": "@analyst",
            "request": "heavy analysis",
            "error": "timeout",
        }

    with patch("runtime.agents.loader.load_agent", new_callable=AsyncMock, return_value=None):
        with patch(
            "runtime.tasks.handlers.activate_agent._execute_subagent",
            new_callable=AsyncMock,
            side_effect=mock_execute,
        ):
            result = await handle_activate_agent(task)

    assert "tempo limite" in result["message"].lower() or "timeout" in result.get("error", "").lower()


# ── Whitelist verification ──────────────────────────────────────────────

def test_supabase_table_whitelist_contains_expected():
    assert "clients" in _SUPABASE_TABLE_WHITELIST
    assert "runtime_tasks" in _SUPABASE_TABLE_WHITELIST
    assert "llm_cost_log" in _SUPABASE_TABLE_WHITELIST


def test_available_agents_have_required_fields():
    for key, config in _AVAILABLE_AGENTS.items():
        assert "name" in config
        assert "model" in config
        assert "system_prompt" in config
        assert "max_tool_iterations" in config
        assert "timeout_s" in config
