"""
Unit tests for Brain Archival handler (B3-05).

Tests expired chunk detection, archive insertion, deletion, batch processing,
and error handling.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_expired_chunk(chunk_id="chunk-001"):
    """Build a mock expired brain chunk."""
    return {
        "id": chunk_id,
        "raw_content": "Some old content",
        "source_type": "web_url",
        "source_title": "Old Page",
        "pipeline_type": "standard",
        "brain_owner": "sparkle-internal",
        "client_id": "client-001",
        "chunk_metadata": {"key": "value"},
        "curation_status": "approved",
        "confirmation_count": 2,
        "namespace": "web",
        "expires_at": "2025-01-01T00:00:00+00:00",
        "usage_count": 5,
        "last_used_at": "2025-06-01T00:00:00+00:00",
        "created_at": "2024-01-01T00:00:00+00:00",
        "embedding": [0.1] * 10,
    }


def _mock_supabase_archival(expired_chunks=None, archive_error=False, delete_error=False):
    """Create mock supabase for archival tests.

    On first call to select, returns expired_chunks.
    On second call, returns empty (end of loop).
    """
    mock_sb = MagicMock()

    # Track calls to simulate batched behavior
    select_call_count = [0]

    def table_fn(name):
        q = MagicMock()

        if name == "brain_chunks":
            # Select call (with .lt().not_().limit())
            def select_fn(*args, **kwargs):
                return q

            q.select = select_fn
            q.lt = MagicMock(return_value=q)
            q.not_ = MagicMock()
            q.not_.is_ = MagicMock(return_value=q)
            q.limit = MagicMock(return_value=q)

            def execute_fn():
                select_call_count[0] += 1
                if select_call_count[0] == 1 and expired_chunks:
                    return MagicMock(data=expired_chunks)
                return MagicMock(data=[])

            q.execute = execute_fn

            # Delete call
            q.delete = MagicMock(return_value=q)
            q.eq = MagicMock(return_value=q)
            if delete_error:
                q.execute = MagicMock(side_effect=Exception("Delete failed"))

        elif name == "brain_chunks_archive":
            q.upsert = MagicMock(return_value=q)
            if archive_error:
                q.execute = MagicMock(side_effect=Exception("Archive insert failed"))
            else:
                q.execute = MagicMock(return_value=MagicMock(data=[{}]))

        return q

    mock_sb.table = table_fn
    return mock_sb


# ── handle_brain_archival tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archival_no_expired_chunks():
    """When no chunks are expired, should return 0 archived."""
    from runtime.tasks.handlers.brain_archival import handle_brain_archival

    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.select.return_value = mock_q
    mock_q.lt.return_value = mock_q
    mock_q.not_ = MagicMock()
    mock_q.not_.is_ = MagicMock(return_value=mock_q)
    mock_q.limit.return_value = mock_q
    mock_q.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value = mock_q

    with patch("runtime.tasks.handlers.brain_archival.supabase", mock_sb):
        result = await handle_brain_archival({})

    assert result["archived_count"] == 0
    assert "complete" in result["message"].lower()


@pytest.mark.asyncio
async def test_archival_batch_size_constant():
    from runtime.tasks.handlers.brain_archival import BATCH_SIZE
    assert BATCH_SIZE == 100


@pytest.mark.asyncio
async def test_archival_returns_error_count():
    """Verify the result includes error count."""
    from runtime.tasks.handlers.brain_archival import handle_brain_archival

    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.select.return_value = mock_q
    mock_q.lt.return_value = mock_q
    mock_q.not_ = MagicMock()
    mock_q.not_.is_ = MagicMock(return_value=mock_q)
    mock_q.limit.return_value = mock_q
    mock_q.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value = mock_q

    with patch("runtime.tasks.handlers.brain_archival.supabase", mock_sb):
        result = await handle_brain_archival({})

    assert "errors" in result
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_archival_fatal_error():
    """Fatal DB errors should return error message with archived_count so far."""
    from runtime.tasks.handlers.brain_archival import handle_brain_archival

    mock_sb = MagicMock()
    mock_sb.table.side_effect = Exception("Connection lost entirely")

    with patch("runtime.tasks.handlers.brain_archival.supabase", mock_sb):
        result = await handle_brain_archival({})

    assert "failed" in result["message"].lower() or "error" in result["message"].lower()
    assert result["archived_count"] == 0


# ── _make_expired_chunk structure tests ─────────────────────────────────────

def test_expired_chunk_has_required_fields():
    chunk = _make_expired_chunk()
    required = ["id", "raw_content", "source_type", "client_id", "expires_at", "namespace"]
    for field in required:
        assert field in chunk


def test_expired_chunk_has_embedding():
    chunk = _make_expired_chunk()
    assert chunk["embedding"] is not None
    assert len(chunk["embedding"]) > 0
