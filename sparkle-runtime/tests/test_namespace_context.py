"""
C2-B3: Tests for namespace context injection utility.

Tests cover:
  - fetch_namespace_context returns formatted string
  - Empty results return empty string
  - Truncation at max_tokens works
  - Higher similarity chunks kept on truncation
  - Each injection point (Friday, agent, Zenya) calls fetch correctly
  - Logging captures namespace, latency
  - Graceful degradation when brain_query fails
  - Edge cases: empty query, empty namespace
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runtime.brain.namespace_context import (
    fetch_namespace_context,
    _format_and_truncate,
    _elapsed_ms,
)


# -- Fixtures ------------------------------------------------------------------


def _make_chunk(
    content: str,
    similarity: float = 0.8,
    source_title: str = "test-source",
    source_type: str = "info",
    brain_owner: str = "mauro-personal",
    curation_status: str = "pending",
    chunk_id: str = "chunk-1",
) -> dict:
    return {
        "id": chunk_id,
        "raw_content": content,
        "similarity": similarity,
        "source_title": source_title,
        "source_type": source_type,
        "brain_owner": brain_owner,
        "curation_status": curation_status,
    }


SAMPLE_CHUNKS = [
    _make_chunk("Sparkle visa democratizar IA para PMEs brasileiras", similarity=0.92, chunk_id="c1"),
    _make_chunk("MRR atual de R$4.594 com 6 clientes ativos", similarity=0.85, chunk_id="c2"),
    _make_chunk("Stack: FastAPI + Claude API + Supabase + Z-API", similarity=0.78, chunk_id="c3"),
]


# -- Test: fetch_namespace_context returns formatted string --------------------


@pytest.mark.asyncio
async def test_fetch_returns_formatted_string():
    """AC-2: Context appears as delimited block [CONTEXTO BRAIN -- namespace]."""
    with patch(
        "runtime.brain.namespace_context._search_namespace",
        new_callable=AsyncMock,
        return_value=SAMPLE_CHUNKS[:1],
    ):
        result = await fetch_namespace_context("mauro-personal", "visao da sparkle")

    assert "[CONTEXTO BRAIN -- mauro-personal]" in result
    assert "[/CONTEXTO BRAIN]" in result
    assert "Sparkle visa democratizar" in result


# -- Test: empty results return empty string -----------------------------------


@pytest.mark.asyncio
async def test_fetch_empty_results_returns_empty():
    """AC-3/AC-8/AC-12: Graceful degradation when no chunks found."""
    with patch(
        "runtime.brain.namespace_context._search_namespace",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await fetch_namespace_context("mauro-personal", "tema desconhecido")

    assert result == ""


# -- Test: empty query returns empty string ------------------------------------


@pytest.mark.asyncio
async def test_fetch_empty_query_returns_empty():
    result = await fetch_namespace_context("mauro-personal", "")
    assert result == ""


# -- Test: empty namespace returns empty string --------------------------------


@pytest.mark.asyncio
async def test_fetch_empty_namespace_returns_empty():
    result = await fetch_namespace_context("", "alguma query")
    assert result == ""


# -- Test: truncation at max_tokens works --------------------------------------


@pytest.mark.asyncio
async def test_truncation_respects_max_tokens():
    """AC-13: Truncates at max_tokens (chars/4 approximation)."""
    # Create chunks that together exceed a tiny budget
    big_chunks = [
        _make_chunk("A" * 200, similarity=0.95, chunk_id="c1"),
        _make_chunk("B" * 200, similarity=0.90, chunk_id="c2"),
        _make_chunk("C" * 200, similarity=0.85, chunk_id="c3"),
        _make_chunk("D" * 200, similarity=0.80, chunk_id="c4"),
    ]
    with patch(
        "runtime.brain.namespace_context._search_namespace",
        new_callable=AsyncMock,
        return_value=big_chunks,
    ):
        # max_tokens=100 -> ~400 chars budget (very small)
        result = await fetch_namespace_context("sparkle-ops", "regras", max_tokens=100)

    # Should have content but be truncated (not all 4 chunks)
    assert len(result) <= 500  # 100 tokens * 4 + some overhead
    # The highest similarity chunk should be present
    assert "A" * 50 in result


# -- Test: higher similarity chunks kept on truncation -------------------------


def test_format_and_truncate_keeps_highest_similarity():
    """AC-13+: When truncating, highest-similarity chunks are kept."""
    chunks = [
        _make_chunk("LOW relevance content here", similarity=0.50, chunk_id="low"),
        _make_chunk("HIGH relevance content here", similarity=0.99, chunk_id="high"),
        _make_chunk("MED relevance content here", similarity=0.75, chunk_id="med"),
    ]
    # Sort like the main function does
    chunks.sort(key=lambda c: c.get("similarity", 0), reverse=True)

    # Tight budget: should only fit ~1 chunk
    result = _format_and_truncate("test-ns", chunks, max_tokens=40)

    assert "HIGH relevance" in result
    # LOW should be excluded due to truncation
    assert "LOW relevance" not in result


# -- Test: logging captures namespace and latency ------------------------------


@pytest.mark.asyncio
async def test_logging_captures_namespace_and_latency(caplog):
    """AC-15: Logging registers namespace, query, chunks, latency."""
    with patch(
        "runtime.brain.namespace_context._search_namespace",
        new_callable=AsyncMock,
        return_value=SAMPLE_CHUNKS[:2],
    ):
        with caplog.at_level(logging.INFO, logger="runtime.brain.namespace_context"):
            await fetch_namespace_context("sparkle-lore", "quem e a zenya")

    log_text = caplog.text
    assert "namespace=sparkle-lore" in log_text
    assert "chunks=2" in log_text
    assert "latency_ms=" in log_text


# -- Test: graceful degradation when search raises exception -------------------


@pytest.mark.asyncio
async def test_graceful_degradation_on_search_error():
    """Never breaks caller even if search fails completely."""
    with patch(
        "runtime.brain.namespace_context._search_namespace",
        new_callable=AsyncMock,
        side_effect=Exception("Supabase connection failed"),
    ):
        result = await fetch_namespace_context("mauro-personal", "qualquer coisa")

    assert result == ""


# -- Test: Friday injection point calls fetch correctly ------------------------


@pytest.mark.asyncio
async def test_friday_chat_calls_namespace_context():
    """AC-1/AC-2: Friday chat handler injects mauro-personal context."""
    mock_context = "[CONTEXTO BRAIN -- mauro-personal]\nVisao de longo prazo...\n[/CONTEXTO BRAIN]"

    with patch(
        "runtime.brain.namespace_context.fetch_namespace_context",
        new_callable=AsyncMock,
        return_value=mock_context,
    ) as mock_fetch, patch(
        "runtime.tasks.handlers.chat.call_claude",
        new_callable=AsyncMock,
        return_value="Resposta da Friday",
    ), patch(
        "runtime.tasks.handlers.chat._get_history",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "runtime.tasks.handlers.chat._save_to_history",
        new_callable=AsyncMock,
    ):
        from runtime.tasks.handlers.chat import handle_chat

        task = {
            "id": "test-task-1",
            "payload": {
                "original_text": "qual a visao de longo prazo?",
                "from_number": "5512999999999",
            },
        }
        result = await handle_chat(task)

        mock_fetch.assert_called_once_with("mauro-personal", "qual a visao de longo prazo?")
        assert result.get("message") == "Resposta da Friday"


# -- Test: Agent activation injects sparkle-ops context ------------------------


@pytest.mark.asyncio
async def test_agent_activation_calls_namespace_context():
    """AC-5/AC-7: activate_agent injects sparkle-ops context."""
    mock_context = "[CONTEXTO BRAIN -- sparkle-ops]\nPipeline regras...\n[/CONTEXTO BRAIN]"

    with patch(
        "runtime.brain.namespace_context.fetch_namespace_context",
        new_callable=AsyncMock,
        return_value=mock_context,
    ) as mock_fetch, patch(
        "runtime.tasks.handlers.activate_agent._client",
    ) as mock_anthropic:
        # Mock the Anthropic API response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Analise concluida.")]
        mock_response.content[0].text = "Analise concluida."
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)

        # Also mock context assembler and cost logging
        with patch(
            "runtime.tasks.handlers.activate_agent.assemble_context",
            new_callable=AsyncMock,
            return_value="",
        ), patch(
            "runtime.tasks.handlers.activate_agent._log_cost_async",
            new_callable=AsyncMock,
        ):
            from runtime.tasks.handlers.activate_agent import _run_subagent, _AVAILABLE_AGENTS

            config = _AVAILABLE_AGENTS["analyst"]
            text, tools, cost = await _run_subagent(
                config, "analisa o MRR", task_id="test-1", agent_key="analyst"
            )

        mock_fetch.assert_called_once_with("sparkle-ops", "analisa o MRR")


# -- Test: Zenya character injects sparkle-lore context ------------------------


@pytest.mark.asyncio
async def test_zenya_character_calls_namespace_context():
    """AC-9/AC-11: send_character_message injects sparkle-lore context."""
    mock_lore = "[CONTEXTO BRAIN -- sparkle-lore]\nZenya nasceu em...\n[/CONTEXTO BRAIN]"

    with patch(
        "runtime.brain.namespace_context.fetch_namespace_context",
        new_callable=AsyncMock,
        return_value=mock_lore,
    ) as mock_fetch, patch(
        "runtime.tasks.handlers.send_character_message.call_claude",
        new_callable=AsyncMock,
        return_value="Ola! Sou a Zenya.",
    ), patch(
        "runtime.tasks.handlers.send_character_message._get_zenya_history",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "runtime.tasks.handlers.send_character_message._save_zenya_history",
        new_callable=AsyncMock,
    ), patch(
        "runtime.tasks.handlers.send_character_message.supabase",
    ):
        from runtime.tasks.handlers.send_character_message import (
            handle_send_character_message,
        )

        task = {
            "id": "test-task-z",
            "client_id": "test-client",
            "payload": {
                "character": "zenya",
                "message": "quem e voce?",
                "phone": "5511999990000",
                "soul_prompt": "Voce e a Zenya.",
                "lore": "",
                "client_name": "Test Client",
            },
        }
        result = await handle_send_character_message(task)

        mock_fetch.assert_called_once_with("sparkle-lore", "quem e voce?")
        assert result.get("message") == "Ola! Sou a Zenya."


# -- Test: _elapsed_ms helper --------------------------------------------------


def test_elapsed_ms():
    import time
    start = time.monotonic()
    time.sleep(0.01)  # 10ms
    elapsed = _elapsed_ms(start)
    assert elapsed >= 5  # at least 5ms (allow some slack)
    assert elapsed < 1000  # less than 1 second
