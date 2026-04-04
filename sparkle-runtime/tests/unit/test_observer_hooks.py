"""
Unit tests for Observer Hooks (B2-06).

Tests post_response_hook: quality log saving, gap creation threshold,
and non-blocking error handling.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_supabase():
    """Return a MagicMock that handles table().insert().execute() chains."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "log-001"}])
    mock_sb.table.return_value = mock_table
    return mock_sb


# ── post_response_hook tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hook_saves_quality_log():
    """Hook should save evaluation results to response_quality_log."""
    from runtime.observer.hooks import post_response_hook

    eval_result = {
        "score": 0.85,
        "scores": {"relevance": 0.9, "completeness": 0.8, "tone": 0.85, "accuracy": 0.9, "safety": 0.8},
        "issues": [],
        "suggestion": None,
        "should_retry": False,
    }
    mock_sb = _mock_supabase()

    with patch("runtime.observer.hooks.evaluate_response_quality", new_callable=AsyncMock, return_value=eval_result), \
         patch("runtime.observer.hooks.supabase", mock_sb):
        await post_response_hook("friday", "What is MRR?", "MRR is recurring revenue.", None)

    # Should have called table("response_quality_log") for the log
    mock_sb.table.assert_any_call("response_quality_log")


@pytest.mark.asyncio
async def test_hook_creates_gap_on_low_score():
    """Score < 0.3 should trigger gap_report creation."""
    from runtime.observer.hooks import post_response_hook, _QUALITY_GAP_THRESHOLD

    eval_result = {
        "score": 0.2,
        "scores": {"relevance": 0.1, "completeness": 0.2, "tone": 0.3, "accuracy": 0.2, "safety": 0.2},
        "issues": ["Completely off-topic"],
        "suggestion": "Re-read the question.",
        "should_retry": True,
    }
    mock_sb = _mock_supabase()

    with patch("runtime.observer.hooks.evaluate_response_quality", new_callable=AsyncMock, return_value=eval_result), \
         patch("runtime.observer.hooks.supabase", mock_sb):
        await post_response_hook("friday", "Deploy?", "Hello!", None)

    # Should have called table("gap_reports") for the gap
    table_calls = [str(c) for c in mock_sb.table.call_args_list]
    assert any("gap_reports" in c for c in table_calls)


@pytest.mark.asyncio
async def test_hook_no_gap_on_good_score():
    """Score >= 0.3 should NOT create a gap_report."""
    from runtime.observer.hooks import post_response_hook

    eval_result = {
        "score": 0.75,
        "scores": {"relevance": 0.8, "completeness": 0.7, "tone": 0.75, "accuracy": 0.8, "safety": 0.7},
        "issues": [],
        "suggestion": None,
        "should_retry": False,
    }
    mock_sb = _mock_supabase()

    with patch("runtime.observer.hooks.evaluate_response_quality", new_callable=AsyncMock, return_value=eval_result), \
         patch("runtime.observer.hooks.supabase", mock_sb):
        await post_response_hook("friday", "Status?", "All systems operational.", None)

    # gap_reports should NOT be called
    table_calls = [str(c) for c in mock_sb.table.call_args_list]
    assert not any("gap_reports" in c for c in table_calls)


@pytest.mark.asyncio
async def test_hook_never_crashes():
    """Hook should catch all exceptions — never block the main response."""
    from runtime.observer.hooks import post_response_hook

    with patch("runtime.observer.hooks.evaluate_response_quality", new_callable=AsyncMock, side_effect=Exception("BOOM")):
        # Should NOT raise
        await post_response_hook("friday", "test", "response", None)


@pytest.mark.asyncio
async def test_hook_handles_db_save_failure():
    """If DB save fails, hook should still complete without crashing."""
    from runtime.observer.hooks import post_response_hook

    eval_result = {"score": 0.8, "scores": {}, "issues": [], "suggestion": None, "should_retry": False}
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_table
    mock_table.execute.side_effect = Exception("DB connection lost")
    mock_sb.table.return_value = mock_table

    with patch("runtime.observer.hooks.evaluate_response_quality", new_callable=AsyncMock, return_value=eval_result), \
         patch("runtime.observer.hooks.supabase", mock_sb):
        # Should NOT raise
        await post_response_hook("friday", "test", "response", None)


# ── Threshold constant test ─────────────────────────────────────────────────

def test_quality_gap_threshold():
    from runtime.observer.hooks import _QUALITY_GAP_THRESHOLD

    assert _QUALITY_GAP_THRESHOLD == 0.3
