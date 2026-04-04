"""
Unit tests for brain_query handler.
Mocks: Supabase, OpenAI embeddings, Claude API.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.tasks.handlers.brain_query import (
    handle_brain_query,
    _format_chunks,
    _text_search,
)


# ── Tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brain_query_empty_query():
    task = {"payload": {}}
    result = await handle_brain_query(task)
    assert "nenhuma query" in result["message"].lower()


@pytest.mark.asyncio
async def test_brain_query_no_results():
    """When no chunks are found, return 'no knowledge' message."""
    task = {"payload": {"query": "quantum computing"}, "id": "task-1"}

    with patch(
        "runtime.tasks.handlers.brain_query._search_knowledge_base",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await handle_brain_query(task)

    assert "ainda não tenho conhecimento" in result["message"]
    assert "quantum computing" in result["message"]


@pytest.mark.asyncio
async def test_brain_query_with_results():
    """When chunks are found, Claude synthesizes a response."""
    chunks = [
        {"type": "note", "content": "Sparkle uses FastAPI runtime", "source": "docs"},
        {"type": "decision", "content": "We chose Supabase for DB", "source": "adr"},
    ]

    task = {"payload": {"query": "what stack does sparkle use"}, "id": "task-2"}

    with patch(
        "runtime.tasks.handlers.brain_query._search_knowledge_base",
        new_callable=AsyncMock,
        return_value=chunks,
    ):
        with patch(
            "runtime.tasks.handlers.brain_query.call_claude",
            new_callable=AsyncMock,
            return_value="Sparkle uses FastAPI + Supabase.",
        ):
            result = await handle_brain_query(task)

    assert "Brain" in result["message"]
    assert "Sparkle uses FastAPI + Supabase." in result["message"]


@pytest.mark.asyncio
async def test_brain_query_uses_original_text_as_fallback():
    """When no 'query' param, falls back to original_text."""
    task = {"payload": {"original_text": "brain, what is sparkle?"}, "id": "task-3"}

    with patch(
        "runtime.tasks.handlers.brain_query._search_knowledge_base",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await handle_brain_query(task)

    assert "ainda não tenho conhecimento" in result["message"]


# ── Format chunks tests ─────────────────────────────────────────────────

def test_format_chunks_basic():
    chunks = [
        {"type": "note", "content": "Content A", "source": "docs"},
        {"type": "decision", "content": "Content B", "source": ""},
    ]
    formatted = _format_chunks(chunks)
    assert "[1]" in formatted
    assert "[2]" in formatted
    assert "Content A" in formatted
    assert "(fonte: docs)" in formatted


def test_format_chunks_truncates_long_content():
    chunks = [{"type": "info", "content": "x" * 1000, "source": ""}]
    formatted = _format_chunks(chunks)
    # Content is truncated at 800 chars
    assert len(formatted) < 1000


def test_format_chunks_empty():
    assert _format_chunks([]) == ""


# ── Text search tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_text_search_filters_short_words():
    """_text_search should filter words <= 3 chars for search terms."""
    mock_response = MagicMock()
    mock_response.data = [{"id": "1", "type": "note", "content": "test", "source": "", "client_id": ""}]

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.text_search.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_query

    with patch("runtime.tasks.handlers.brain_query.supabase", mock_sb):
        results = await _text_search("how does the runtime work exactly")

    assert len(results) == 1
