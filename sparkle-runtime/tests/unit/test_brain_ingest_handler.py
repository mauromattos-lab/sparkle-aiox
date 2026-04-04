"""
Unit tests for brain_ingest handler.
Mocks: Supabase, OpenAI embeddings.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.tasks.handlers.brain_ingest import (
    handle_brain_ingest,
    canonicalize_entities,
    _COMMAND_PREFIX_RE,
)


# ── Helper: mock supabase for brain_ingest ──────────────────────────────

def _mock_supabase_insert(row_data=None):
    """Returns a mock supabase that responds to table().insert().execute()."""
    mock_response = MagicMock()
    mock_response.data = [{"id": "chunk-uuid-001", **(row_data or {})}]

    mock_query = MagicMock()
    mock_query.insert.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_query
    return mock_sb


def _mock_supabase_entities(entities=None):
    """Returns a mock supabase that responds to brain_entities query."""
    mock_response = MagicMock()
    mock_response.data = entities or []

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_sb = MagicMock()

    def table_router(name):
        if name == "brain_entities":
            return mock_query
        # For brain_chunks insert
        insert_resp = MagicMock()
        insert_resp.data = [{"id": "chunk-uuid-001"}]
        insert_query = MagicMock()
        insert_query.insert.return_value = insert_query
        insert_query.execute.return_value = insert_resp
        return insert_query

    mock_sb.table.side_effect = table_router
    return mock_sb


# ── Tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brain_ingest_empty_content():
    task = {"payload": {}}
    result = await handle_brain_ingest(task)
    assert "não recebi conteúdo" in result["message"].lower() or "não recebi" in result["message"]


@pytest.mark.asyncio
async def test_brain_ingest_strips_command_prefix():
    """Verify command prefixes like 'brain, aprende isso:' are stripped."""
    assert _COMMAND_PREFIX_RE.sub("", "brain, aprende isso: test content").strip() == "test content"
    assert _COMMAND_PREFIX_RE.sub("", "salva: important note").strip() == "important note"
    assert _COMMAND_PREFIX_RE.sub("", "registra: something new").strip() == "something new"


@pytest.mark.asyncio
async def test_brain_ingest_content_after_prefix_strip_empty():
    """If content is empty after stripping prefix, return error."""
    task = {
        "payload": {
            "content": "brain, aprende isso:",
            "ingest_type": "friday_ingest",
        }
    }
    with patch("runtime.tasks.handlers.brain_ingest.supabase", _mock_supabase_entities()):
        with patch("runtime.tasks.handlers.brain_ingest._get_embedding", new_callable=AsyncMock, return_value=None):
            result = await handle_brain_ingest(task)
    # After stripping "brain, aprende isso:" only ":" remains -> stripped to empty
    assert "vazio" in result["message"].lower() or "não recebi" in result["message"].lower()


@pytest.mark.asyncio
async def test_brain_ingest_success_without_embedding():
    """Successful ingest with no OpenAI key (embedding=None)."""
    mock_sb = _mock_supabase_entities()

    task = {
        "payload": {
            "content": "The quick brown fox jumps over the lazy dog",
            "source_agent": "test",
            "ingest_type": "agent_output",
        },
        "client_id": "sparkle-internal",
        "id": "task-123",
    }

    with patch("runtime.tasks.handlers.brain_ingest.supabase", mock_sb):
        with patch("runtime.tasks.handlers.brain_ingest._get_embedding", new_callable=AsyncMock, return_value=None):
            result = await handle_brain_ingest(task)

    assert "Anotado no Brain" in result["message"]
    assert result["chunk_id"] == "chunk-uuid-001"
    assert result["embedded"] is False


@pytest.mark.asyncio
async def test_brain_ingest_success_with_embedding():
    """Successful ingest with embedding."""
    mock_sb = _mock_supabase_entities()
    fake_embedding = [0.1] * 1536

    task = {
        "payload": {
            "content": "Important knowledge about the Sparkle system",
            "source_agent": "architect",
            "ingest_type": "adr",
        },
        "client_id": "sparkle-internal",
        "id": "task-456",
    }

    with patch("runtime.tasks.handlers.brain_ingest.supabase", mock_sb):
        with patch("runtime.tasks.handlers.brain_ingest._get_embedding", new_callable=AsyncMock, return_value=fake_embedding):
            result = await handle_brain_ingest(task)

    assert "Anotado no Brain" in result["message"]
    assert result["embedded"] is True
    assert "embedding vetorial" in result["message"]


@pytest.mark.asyncio
async def test_brain_ingest_with_entity_refs():
    """Entity refs from payload are included in tags."""
    mock_sb = _mock_supabase_entities()

    task = {
        "payload": {
            "content": "Mauro decided to increase pricing",
            "entity_refs": ["Mauro Mattos", "Sparkle AIOX"],
            "source_agent": "friday",
        },
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.brain_ingest.supabase", mock_sb):
        with patch("runtime.tasks.handlers.brain_ingest._get_embedding", new_callable=AsyncMock, return_value=None):
            result = await handle_brain_ingest(task)

    assert "Mauro Mattos" in result["entity_tags"]
    assert "Sparkle AIOX" in result["entity_tags"]


@pytest.mark.asyncio
async def test_brain_ingest_db_error():
    """If Supabase insert fails, return error message."""
    mock_sb = MagicMock()

    def table_router(name):
        if name == "brain_entities":
            resp = MagicMock()
            resp.data = []
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = resp
            return q
        # brain_chunks insert fails
        q = MagicMock()
        q.insert.side_effect = Exception("Connection refused")
        return q

    mock_sb.table.side_effect = table_router

    task = {
        "payload": {"content": "Some content to ingest", "source_agent": "test"},
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.brain_ingest.supabase", mock_sb):
        with patch("runtime.tasks.handlers.brain_ingest._get_embedding", new_callable=AsyncMock, return_value=None):
            result = await handle_brain_ingest(task)

    assert "erro" in result["message"].lower()


# ── Canonicalization tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_canonicalize_replaces_aliases():
    """canonicalize_entities replaces aliases with canonical names."""
    entities = [
        {
            "canonical_name": "Mauro Mattos",
            "aliases": ["mauro", "o mauro", "mattos"],
            "entity_type": "person",
        }
    ]

    with patch("runtime.tasks.handlers.brain_ingest._get_entity_registry", new_callable=AsyncMock, return_value=entities):
        text, refs = await canonicalize_entities("mauro decidiu aumentar precos", "client-1")

    assert "Mauro Mattos" in text
    assert "Mauro Mattos" in refs


@pytest.mark.asyncio
async def test_canonicalize_no_entities():
    """When no entities exist, text passes through unchanged."""
    with patch("runtime.tasks.handlers.brain_ingest._get_entity_registry", new_callable=AsyncMock, return_value=[]):
        text, refs = await canonicalize_entities("some random text", "client-1")

    assert text == "some random text"
    assert refs == []
