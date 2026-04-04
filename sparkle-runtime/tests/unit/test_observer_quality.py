"""
Unit tests for Observer Quality module (B2-06).

Tests Haiku evaluation parsing, score calculation, fallback behavior,
and the post_response_hook (non-blocking quality gate).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── _parse_eval_response tests ──────────────────────────────────────────────

def test_parse_eval_clean_json():
    from runtime.observer.quality import _parse_eval_response

    raw = json.dumps({
        "scores": {"relevance": 0.9, "completeness": 0.8, "tone": 0.85, "accuracy": 0.95, "safety": 1.0},
        "issues": [],
        "suggestion": None,
    })
    result = _parse_eval_response(raw)
    assert result is not None
    assert result["scores"]["relevance"] == 0.9


def test_parse_eval_with_markdown_fences():
    from runtime.observer.quality import _parse_eval_response

    raw = '```json\n{"scores": {"relevance": 0.5}, "issues": [], "suggestion": null}\n```'
    result = _parse_eval_response(raw)
    assert result is not None
    assert result["scores"]["relevance"] == 0.5


def test_parse_eval_invalid_json():
    from runtime.observer.quality import _parse_eval_response

    result = _parse_eval_response("This is not JSON")
    assert result is None


def test_parse_eval_empty():
    from runtime.observer.quality import _parse_eval_response

    result = _parse_eval_response("")
    assert result is None


# ── _fallback_result tests ──────────────────────────────────────────────────

def test_fallback_result_default():
    from runtime.observer.quality import _fallback_result

    result = _fallback_result()
    assert result["score"] == 0.5
    assert result["should_retry"] is False
    assert result["issues"] == []
    assert result["suggestion"] is None
    # All 5 criteria should be 0.5
    for key in ("relevance", "completeness", "tone", "accuracy", "safety"):
        assert result["scores"][key] == 0.5


def test_fallback_result_with_error():
    from runtime.observer.quality import _fallback_result

    result = _fallback_result(error="Connection timeout")
    assert len(result["issues"]) == 1
    assert "Connection timeout" in result["issues"][0]


# ── evaluate_response_quality tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_high_quality():
    from runtime.observer.quality import evaluate_response_quality

    haiku_response = json.dumps({
        "scores": {"relevance": 0.95, "completeness": 0.9, "tone": 0.85, "accuracy": 0.9, "safety": 1.0},
        "issues": [],
        "suggestion": None,
    })

    with patch("runtime.observer.quality.call_claude", new_callable=AsyncMock, return_value=haiku_response):
        result = await evaluate_response_quality("friday", "What is MRR?", "MRR is Monthly Recurring Revenue.")

    assert result["score"] > 0.8
    assert result["should_retry"] is False
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_evaluate_low_quality_triggers_retry():
    from runtime.observer.quality import evaluate_response_quality

    haiku_response = json.dumps({
        "scores": {"relevance": 0.2, "completeness": 0.3, "tone": 0.4, "accuracy": 0.3, "safety": 0.3},
        "issues": ["Off-topic response", "Missing key details"],
        "suggestion": "Re-read the user question.",
    })

    with patch("runtime.observer.quality.call_claude", new_callable=AsyncMock, return_value=haiku_response):
        result = await evaluate_response_quality("friday", "Deploy status?", "Hello there!")

    assert result["score"] < 0.5
    assert result["should_retry"] is True
    assert len(result["issues"]) == 2


@pytest.mark.asyncio
async def test_evaluate_unparseable_response():
    from runtime.observer.quality import evaluate_response_quality

    with patch("runtime.observer.quality.call_claude", new_callable=AsyncMock, return_value="Not valid JSON at all"):
        result = await evaluate_response_quality("friday", "test", "test response")

    # Should return fallback
    assert result["score"] == 0.5
    assert result["should_retry"] is False


@pytest.mark.asyncio
async def test_evaluate_llm_exception():
    from runtime.observer.quality import evaluate_response_quality

    with patch("runtime.observer.quality.call_claude", new_callable=AsyncMock, side_effect=Exception("API down")):
        result = await evaluate_response_quality("friday", "test", "test response")

    assert result["score"] == 0.5
    assert "API down" in str(result["issues"])


@pytest.mark.asyncio
async def test_evaluate_score_calculation():
    from runtime.observer.quality import evaluate_response_quality

    haiku_response = json.dumps({
        "scores": {"relevance": 1.0, "completeness": 0.8, "tone": 0.6, "accuracy": 0.4, "safety": 0.2},
        "issues": ["Low safety score"],
        "suggestion": "Check for data leaks.",
    })

    with patch("runtime.observer.quality.call_claude", new_callable=AsyncMock, return_value=haiku_response):
        result = await evaluate_response_quality("friday", "test", "response")

    expected_avg = (1.0 + 0.8 + 0.6 + 0.4 + 0.2) / 5  # 0.6
    assert abs(result["score"] - expected_avg) < 0.01
    assert result["scores"]["relevance"] == 1.0
    assert result["scores"]["safety"] == 0.2


@pytest.mark.asyncio
async def test_evaluate_handles_non_list_issues():
    from runtime.observer.quality import evaluate_response_quality

    haiku_response = json.dumps({
        "scores": {"relevance": 0.8, "completeness": 0.8, "tone": 0.8, "accuracy": 0.8, "safety": 0.8},
        "issues": "single issue string",
        "suggestion": 42,
    })

    with patch("runtime.observer.quality.call_claude", new_callable=AsyncMock, return_value=haiku_response):
        result = await evaluate_response_quality("friday", "test", "response")

    assert isinstance(result["issues"], list)
    assert isinstance(result["suggestion"], str)
