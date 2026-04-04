"""
Unit tests for extract_insights handler.
Mocks: Supabase, Claude API, OpenAI embeddings, dedup.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.tasks.handlers.extract_insights import (
    handle_extract_insights,
    _clean_json,
    _CANONICAL_DOMAINS,
)


# ── _clean_json tests ───────────────────────────────────────────────────

def test_clean_json_strips_markdown_fences():
    raw = '```json\n{"insights": []}\n```'
    assert _clean_json(raw) == '{"insights": []}'


def test_clean_json_fixes_truncated():
    raw = '{"insights": [{"title": "test"'
    cleaned = _clean_json(raw)
    # Should close the open brackets
    assert cleaned.endswith("}")


def test_clean_json_passthrough_valid():
    raw = '{"insights": [{"title": "ok"}]}'
    assert _clean_json(raw) == raw


# ── Canonical domains ───────────────────────────────────────────────────

def test_canonical_domains_include_key_domains():
    assert "content_strategy" in _CANONICAL_DOMAINS
    assert "ai_development" in _CANONICAL_DOMAINS
    assert "geral" in _CANONICAL_DOMAINS
    assert "prompt_engineering" in _CANONICAL_DOMAINS


# ── Handler tests ───────────────────────────────────────────────────────

def _make_mock_sb(chunks=None):
    """Build mock supabase for extract_insights."""
    mock_sb = MagicMock()

    def table_fn(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.in_.return_value = q
        q.limit.return_value = q
        q.update.return_value = q

        if name == "brain_chunks":
            resp = MagicMock()
            resp.data = chunks or []
            q.execute.return_value = resp
        elif name == "brain_insights":
            resp = MagicMock()
            resp.data = [{"id": "insight-001"}]
            q.insert.return_value = q
            q.execute.return_value = resp
        else:
            resp = MagicMock()
            resp.data = []
            q.execute.return_value = resp

        return q

    mock_sb.table = table_fn
    return mock_sb


@pytest.mark.asyncio
async def test_extract_insights_no_chunks():
    """When no chunks are found, should return 0 processed."""
    mock_sb = _make_mock_sb(chunks=[])

    task = {
        "payload": {"source_chunk_ids": ["nonexistent-id"]},
        "id": "task-1",
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.extract_insights.supabase", mock_sb):
        result = await handle_extract_insights(task)

    assert result["processed"] == 0
    assert result["inserted"] == 0


@pytest.mark.asyncio
async def test_extract_insights_dry_run():
    """Dry run should classify but not insert."""
    chunks = [
        {
            "id": "chunk-1",
            "raw_content": "Nunca coloque CTA como comando direto — embuta no fluxo narrativo. Isso funciona melhor para engagement.",
            "canonical_content": None,
            "source_title": "video-hannah",
            "chunk_metadata": {},
            "processed_stages": [],
        }
    ]
    mock_sb = _make_mock_sb(chunks=chunks)

    llm_response = json.dumps({
        "insights": [
            {
                "domain": "content_strategy",
                "insight_type": "tecnica",
                "title": "CTA embutido no fluxo",
                "content": "Embuta CTAs no fluxo narrativo em vez de comandos diretos",
                "application": "Ao criar posts Instagram, coloque CTA como continuacao natural",
                "tags": ["cta", "engagement"],
                "confidence": 0.92,
            }
        ]
    })

    task = {
        "payload": {"source_chunk_ids": ["chunk-1"], "dry_run": True},
        "id": "task-1",
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.extract_insights.supabase", mock_sb):
        with patch(
            "runtime.tasks.handlers.extract_insights.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await handle_extract_insights(task)

    assert result["dry_run"] is True
    assert result["processed"] == 1
    assert result["inserted"] == 1  # counted but not actually inserted
    assert "content_strategy" in result["domain_distribution"]


@pytest.mark.asyncio
async def test_extract_insights_filters_low_confidence():
    """Insights below min_confidence should be skipped."""
    chunks = [
        {
            "id": "chunk-2",
            "raw_content": "Some ambiguous content about maybe doing something with marketing perhaps.",
            "canonical_content": None,
            "source_title": "random",
            "chunk_metadata": {},
            "processed_stages": [],
        }
    ]
    mock_sb = _make_mock_sb(chunks=chunks)

    llm_response = json.dumps({
        "insights": [
            {
                "domain": "geral",
                "insight_type": "heuristica",
                "title": "Vague idea",
                "content": "Maybe try marketing",
                "application": "Unknown",
                "tags": [],
                "confidence": 0.3,  # Below default 0.6 threshold
            }
        ]
    })

    task = {
        "payload": {"source_chunk_ids": ["chunk-2"], "dry_run": True},
        "id": "task-2",
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.extract_insights.supabase", mock_sb):
        with patch(
            "runtime.tasks.handlers.extract_insights.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await handle_extract_insights(task)

    assert result["inserted"] == 0  # filtered out by confidence


@pytest.mark.asyncio
async def test_extract_insights_normalizes_hallucinated_domain():
    """If LLM returns a domain not in canonical list, fallback to 'geral'."""
    chunks = [
        {
            "id": "chunk-3",
            "raw_content": "Important insight about blockchain for business applications.",
            "canonical_content": None,
            "source_title": "video",
            "chunk_metadata": {},
            "processed_stages": [],
        }
    ]
    mock_sb = _make_mock_sb(chunks=chunks)

    llm_response = json.dumps({
        "insights": [
            {
                "domain": "blockchain_strategy",  # Not in canonical list
                "insight_type": "framework",
                "title": "Blockchain for business",
                "content": "Use blockchain for transparency",
                "application": "Apply in supply chain",
                "tags": ["blockchain"],
                "confidence": 0.85,
            }
        ]
    })

    task = {
        "payload": {"source_chunk_ids": ["chunk-3"], "dry_run": True},
        "id": "task-3",
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.extract_insights.supabase", mock_sb):
        with patch(
            "runtime.tasks.handlers.extract_insights.call_claude",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await handle_extract_insights(task)

    # Should have been normalized to "geral"
    assert "geral" in result["domain_distribution"]


@pytest.mark.asyncio
async def test_extract_insights_skips_short_chunks():
    """Chunks with < 30 chars of content should be skipped."""
    chunks = [
        {
            "id": "chunk-short",
            "raw_content": "too short",
            "canonical_content": None,
            "source_title": "",
            "chunk_metadata": {},
            "processed_stages": [],
        }
    ]
    mock_sb = _make_mock_sb(chunks=chunks)

    task = {
        "payload": {"source_chunk_ids": ["chunk-short"]},
        "id": "task-4",
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.extract_insights.supabase", mock_sb):
        result = await handle_extract_insights(task)

    assert result["processed"] == 1
    assert result["inserted"] == 0


@pytest.mark.asyncio
async def test_extract_insights_handles_invalid_json():
    """If Claude returns invalid JSON, should skip that chunk gracefully."""
    chunks = [
        {
            "id": "chunk-bad-json",
            "raw_content": "Valid long content that should be processed by Claude for insights extraction.",
            "canonical_content": None,
            "source_title": "test",
            "chunk_metadata": {},
            "processed_stages": [],
        }
    ]
    mock_sb = _make_mock_sb(chunks=chunks)

    task = {
        "payload": {"source_chunk_ids": ["chunk-bad-json"], "dry_run": True},
        "id": "task-5",
        "client_id": "sparkle-internal",
    }

    with patch("runtime.tasks.handlers.extract_insights.supabase", mock_sb):
        with patch(
            "runtime.tasks.handlers.extract_insights.call_claude",
            new_callable=AsyncMock,
            return_value="This is not valid JSON at all!",
        ):
            result = await handle_extract_insights(task)

    assert result["processed"] == 1
    assert result["inserted"] == 0  # JSON parse failed, no insights extracted
