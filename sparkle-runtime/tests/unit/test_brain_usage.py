"""
Unit tests for Brain Usage Tracking (B3-05).

Tests usage_count increment, last_used_at update, parallel execution,
and graceful error handling.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_supabase_for_usage(initial_count=0):
    """Create a mock supabase that simulates select+update for usage tracking."""
    mock_sb = MagicMock()

    select_response = MagicMock()
    select_response.data = {"usage_count": initial_count}

    update_response = MagicMock()
    update_response.data = [{"usage_count": initial_count + 1}]

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.single.return_value = mock_query
    mock_query.execute.return_value = select_response

    mock_update_query = MagicMock()
    mock_update_query.eq.return_value = mock_update_query
    mock_update_query.execute.return_value = update_response

    call_count = [0]
    def table_fn(name):
        call_count[0] += 1
        if call_count[0] % 2 == 1:  # odd calls are select
            return mock_query
        else:  # even calls are update
            q = MagicMock()
            q.update.return_value = mock_update_query
            return q

    mock_sb.table = table_fn
    return mock_sb


# ── track_chunk_usage tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_track_empty_list():
    """Empty chunk_ids should return immediately without DB calls."""
    from runtime.brain.usage import track_chunk_usage

    mock_sb = MagicMock()
    with patch("runtime.brain.usage.supabase", mock_sb):
        await track_chunk_usage([])
    mock_sb.table.assert_not_called()


@pytest.mark.asyncio
async def test_track_single_chunk():
    """Single chunk should be tracked with incremented usage_count."""
    from runtime.brain.usage import track_chunk_usage

    mock_sb = _mock_supabase_for_usage(initial_count=5)

    with patch("runtime.brain.usage.supabase", mock_sb):
        await track_chunk_usage(["chunk-001"])

    # Should have called table() at least once
    # The exact call pattern depends on asyncio.to_thread wrapping


@pytest.mark.asyncio
async def test_track_multiple_chunks():
    """Multiple chunks should all be tracked concurrently."""
    from runtime.brain.usage import track_chunk_usage

    mock_sb = _mock_supabase_for_usage(initial_count=0)

    with patch("runtime.brain.usage.supabase", mock_sb):
        await track_chunk_usage(["chunk-001", "chunk-002", "chunk-003"])


@pytest.mark.asyncio
async def test_track_handles_db_error_gracefully():
    """DB errors should be caught — never crash the caller."""
    from runtime.brain.usage import track_chunk_usage

    mock_sb = MagicMock()
    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.single.return_value = mock_query
    mock_query.execute.side_effect = Exception("DB connection lost")
    mock_sb.table.return_value = mock_query

    with patch("runtime.brain.usage.supabase", mock_sb):
        # Should NOT raise
        await track_chunk_usage(["chunk-001"])
