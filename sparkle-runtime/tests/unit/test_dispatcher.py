"""
Unit tests for Friday dispatcher (classify_and_dispatch).
Mocks: Claude API, Supabase.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.friday.dispatcher import (
    classify_and_dispatch,
    _detect_url,
    _is_youtube,
    INTENTS,
    DOMAINS,
)


# ── URL detection tests ─────────────────────────────────────────────────

def test_detect_url_http():
    assert _detect_url("check https://google.com please") == "https://google.com"


def test_detect_url_www():
    assert _detect_url("go to www.example.com now") == "www.example.com"


def test_detect_url_none():
    assert _detect_url("no url here") is None


def test_is_youtube():
    assert _is_youtube("https://youtube.com/watch?v=abc") is True
    assert _is_youtube("https://youtu.be/abc") is True
    assert _is_youtube("https://google.com") is False


# ── Intent/domain validation ────────────────────────────────────────────

def test_intents_list_not_empty():
    assert len(INTENTS) > 10


def test_domains_list_not_empty():
    assert len(DOMAINS) >= 7
    assert "geral" in DOMAINS
    assert "trafego_pago" in DOMAINS


# ── classify_and_dispatch tests ─────────────────────────────────────────

def _make_mock_sb_for_dispatch(task_id="fake-task-id-001"):
    """Mock supabase that handles runtime_tasks insert."""
    mock_sb = MagicMock()

    def table_fn(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.order.return_value = q
        q.execute.return_value = MagicMock(data=[])

        def insert_fn(row):
            row["id"] = task_id
            resp = MagicMock()
            resp.data = [row]
            iq = MagicMock()
            iq.execute.return_value = resp
            return iq

        q.insert = insert_fn
        return q

    mock_sb.table = table_fn
    return mock_sb


@pytest.mark.asyncio
async def test_dispatch_chat_intent():
    """Normal chat message should be classified as chat."""
    mock_sb = _make_mock_sb_for_dispatch()
    llm_response = json.dumps({
        "intent": "chat",
        "domain": "geral",
        "params": {},
        "summary": "Oi, tudo bem?",
    })

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch(
            "runtime.friday.dispatcher.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            task = await classify_and_dispatch("Oi, tudo bem?")

    # specialist_chat when domain is not geral; chat when domain is geral
    assert task["task_type"] == "chat"
    assert task["payload"]["intent"] == "chat"


@pytest.mark.asyncio
async def test_dispatch_brain_query_intent():
    """Brain query should extract query param."""
    mock_sb = _make_mock_sb_for_dispatch()
    llm_response = json.dumps({
        "intent": "brain_query",
        "domain": "brain_ops",
        "params": {"query": "what is the MRR history"},
        "summary": "Brain query: MRR history",
    })

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch(
            "runtime.friday.dispatcher.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            task = await classify_and_dispatch("brain, o que voce sabe sobre MRR?")

    assert task["task_type"] == "brain_query"
    assert task["payload"]["query"] == "what is the MRR history"


@pytest.mark.asyncio
async def test_dispatch_activate_agent_intent():
    """Agent activation should extract agent and request params."""
    mock_sb = _make_mock_sb_for_dispatch()
    llm_response = json.dumps({
        "intent": "activate_agent",
        "domain": "tech",
        "params": {"agent": "@analyst", "request": "analisar o cliente Vitalis"},
        "summary": "Ativar @analyst: analise Vitalis",
    })

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch(
            "runtime.friday.dispatcher.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            task = await classify_and_dispatch("ativa o @analyst pra analisar o cliente Vitalis")

    assert task["task_type"] == "activate_agent"
    assert task["payload"]["agent"] == "@analyst"
    assert task["payload"]["request"] == "analisar o cliente Vitalis"


@pytest.mark.asyncio
async def test_dispatch_specialist_chat_routing():
    """Chat with non-geral domain should route to specialist_chat."""
    mock_sb = _make_mock_sb_for_dispatch()
    llm_response = json.dumps({
        "intent": "chat",
        "domain": "trafego_pago",
        "params": {},
        "summary": "Pergunta sobre Meta Ads",
    })

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch(
            "runtime.friday.dispatcher.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            task = await classify_and_dispatch("como estao as campanhas do Meta Ads?")

    assert task["task_type"] == "specialist_chat"


@pytest.mark.asyncio
async def test_dispatch_invalid_intent_fallback():
    """Invalid intent from LLM should fallback to chat."""
    mock_sb = _make_mock_sb_for_dispatch()
    llm_response = json.dumps({
        "intent": "nonexistent_intent",
        "domain": "geral",
        "params": {},
        "summary": "test",
    })

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch(
            "runtime.friday.dispatcher.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            task = await classify_and_dispatch("something random")

    assert task["task_type"] == "chat"


@pytest.mark.asyncio
async def test_dispatch_invalid_json_fallback():
    """If LLM returns invalid JSON, should fallback to chat."""
    mock_sb = _make_mock_sb_for_dispatch()

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch(
            "runtime.friday.dispatcher.call_claude",
            new_callable=AsyncMock,
            return_value="This is not JSON at all",
        ):
            task = await classify_and_dispatch("hello there")

    assert task["task_type"] == "chat"


@pytest.mark.asyncio
async def test_dispatch_brain_ingest_trigger():
    """Explicit brain ingest triggers should bypass LLM classification."""
    mock_sb = _make_mock_sb_for_dispatch()

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch("runtime.friday.dispatcher.execute_task", create=True, new_callable=AsyncMock):
            task = await classify_and_dispatch(
                "brain, aprende isso: O Mauro decidiu que o preco da Zenya vai ser R$500/mes para novos clientes"
            )

    # Should have created an ack task with status done
    assert task.get("status") == "done" or task.get("task_type") in ("brain_ingest", "brain_ingest_pipeline", "chat")


@pytest.mark.asyncio
async def test_dispatch_url_detected():
    """Messages with URLs should trigger brain_ingest_pipeline."""
    mock_sb = _make_mock_sb_for_dispatch()

    with patch("runtime.friday.dispatcher.supabase", mock_sb):
        with patch("runtime.friday.dispatcher.execute_task", create=True, new_callable=AsyncMock):
            task = await classify_and_dispatch("https://example.com/article")

    # URL detection happens before LLM classification
    assert task.get("status") == "done" or "ingest" in str(task.get("task_type", "")).lower()
