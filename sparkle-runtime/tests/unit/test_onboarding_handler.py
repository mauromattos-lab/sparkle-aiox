"""
Unit tests for Onboarding Handler (B3-03).

Tests the 6-step onboarding pipeline: client creation, website ingest,
DNA extraction, soul_prompt generation, character creation, and state init.
All DB and handler calls are mocked.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _base_task(**payload_overrides):
    """Build a minimal onboarding task."""
    payload = {
        "business_name": "Confeitaria Maria",
        "website_url": "mariaconfeitaria.com.br",
        "instagram_handle": "@mariaconfeitaria",
        "contact_phone": "5511999999999",
    }
    payload.update(payload_overrides)
    return {"id": "task-onboarding-001", "task_type": "onboard_client", "payload": payload}


def _mock_supabase_onboarding():
    """Create mock supabase for onboarding tests."""
    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.upsert.return_value = mock_q
    mock_q.select.return_value = mock_q
    mock_q.eq.return_value = mock_q
    mock_q.order.return_value = mock_q
    mock_q.execute.return_value = MagicMock(data=[{"id": "char-001", "slug": "zenya-confeitaria-maria"}])
    mock_sb.table.return_value = mock_q
    return mock_sb


# ── _log_step tests ─────────────────────────────────────────────────────────

def test_log_step():
    from runtime.onboarding.handler import _log_step

    steps = []
    _log_step(steps, "create_client", "ok", "client_id=abc123")
    assert len(steps) == 1
    assert steps[0]["step"] == "create_client"
    assert steps[0]["status"] == "ok"
    assert "abc123" in steps[0]["detail"]
    assert "timestamp" in steps[0]


def test_log_step_accumulates():
    from runtime.onboarding.handler import _log_step

    steps = []
    _log_step(steps, "step1", "ok", "")
    _log_step(steps, "step2", "warning", "something")
    _log_step(steps, "step3", "error", "failed")
    assert len(steps) == 3


# ── handle_onboarding tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_onboarding_missing_business_name():
    from runtime.onboarding.handler import handle_onboarding

    result = await handle_onboarding({"payload": {}})
    assert result["status"] == "error"
    assert "business_name" in result["error"].lower()


@pytest.mark.asyncio
async def test_onboarding_empty_business_name():
    from runtime.onboarding.handler import handle_onboarding

    result = await handle_onboarding({"payload": {"business_name": "  "}})
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_onboarding_success_full_pipeline():
    from runtime.onboarding.handler import handle_onboarding

    mock_sb = _mock_supabase_onboarding()
    mock_ingest = AsyncMock(return_value={"chunks_inserted": 5})
    mock_dna = AsyncMock(return_value={"total_items": 10, "items_extracted": 10})
    mock_prompt = AsyncMock(return_value="Voce e Zenya da Confeitaria Maria.")
    mock_state = AsyncMock(return_value={"mood": "neutral", "energy": 0.75})

    with patch("runtime.onboarding.handler.supabase", mock_sb), \
         patch("runtime.onboarding.handler._ingest_website", mock_ingest), \
         patch("runtime.onboarding.handler._extract_dna", mock_dna), \
         patch("runtime.onboarding.handler._generate_soul_prompt", mock_prompt), \
         patch("runtime.onboarding.handler._create_character_state", mock_state), \
         patch("runtime.onboarding.handler._save_onboarding_progress", new_callable=AsyncMock):
        result = await handle_onboarding(_base_task())

    assert result["status"] == "draft"
    assert result["client_id"] is not None
    assert "confeitaria" in result["character_slug"].lower() or result["character_slug"] != ""
    assert result["soul_prompt_length"] > 0
    assert len(result["steps"]) >= 5  # at least 5 steps tracked


@pytest.mark.asyncio
async def test_onboarding_no_website_skips_ingest():
    from runtime.onboarding.handler import handle_onboarding

    mock_sb = _mock_supabase_onboarding()
    mock_state = AsyncMock(return_value={"mood": "neutral", "energy": 0.75})

    with patch("runtime.onboarding.handler.supabase", mock_sb), \
         patch("runtime.onboarding.handler._generate_soul_prompt", new_callable=AsyncMock, return_value=""), \
         patch("runtime.onboarding.handler._create_character_state", mock_state), \
         patch("runtime.onboarding.handler._save_onboarding_progress", new_callable=AsyncMock):
        result = await handle_onboarding(_base_task(website_url=""))

    assert result["status"] == "draft"
    # ingest_website step should be "skipped"
    ingest_step = next((s for s in result["steps"] if s["step"] == "ingest_website"), None)
    assert ingest_step is not None
    assert ingest_step["status"] == "skipped"


@pytest.mark.asyncio
async def test_onboarding_client_creation_failure_stops_pipeline():
    from runtime.onboarding.handler import handle_onboarding

    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.upsert.return_value = mock_q
    mock_q.execute.side_effect = Exception("DB write failed")
    mock_sb.table.return_value = mock_q

    with patch("runtime.onboarding.handler.supabase", mock_sb), \
         patch("runtime.onboarding.handler._save_onboarding_progress", new_callable=AsyncMock):
        result = await handle_onboarding(_base_task())

    assert result["status"] == "error"
    assert "cliente" in result["error"].lower() or "client" in result["error"].lower()


@pytest.mark.asyncio
async def test_onboarding_ingest_failure_continues():
    """Website ingest failure should be non-blocking (warning, not error)."""
    from runtime.onboarding.handler import handle_onboarding

    mock_sb = _mock_supabase_onboarding()
    mock_ingest = AsyncMock(side_effect=Exception("Website unreachable"))
    mock_state = AsyncMock(return_value={"mood": "neutral", "energy": 0.75})

    with patch("runtime.onboarding.handler.supabase", mock_sb), \
         patch("runtime.onboarding.handler._ingest_website", mock_ingest), \
         patch("runtime.onboarding.handler._generate_soul_prompt", new_callable=AsyncMock, return_value=""), \
         patch("runtime.onboarding.handler._create_character_state", mock_state), \
         patch("runtime.onboarding.handler._save_onboarding_progress", new_callable=AsyncMock):
        result = await handle_onboarding(_base_task())

    assert result["status"] == "draft"  # pipeline continues despite ingest failure
    ingest_step = next((s for s in result["steps"] if s["step"] == "ingest_website"), None)
    assert ingest_step["status"] == "warning"


@pytest.mark.asyncio
async def test_onboarding_generates_uuid_when_no_client_id():
    from runtime.onboarding.handler import handle_onboarding

    mock_sb = _mock_supabase_onboarding()
    mock_state = AsyncMock(return_value={"mood": "neutral", "energy": 0.75})

    with patch("runtime.onboarding.handler.supabase", mock_sb), \
         patch("runtime.onboarding.handler._ingest_website", new_callable=AsyncMock, return_value={"chunks_inserted": 0}), \
         patch("runtime.onboarding.handler._generate_soul_prompt", new_callable=AsyncMock, return_value=""), \
         patch("runtime.onboarding.handler._create_character_state", mock_state), \
         patch("runtime.onboarding.handler._save_onboarding_progress", new_callable=AsyncMock):
        result = await handle_onboarding(_base_task())

    # client_id should be a UUID string
    assert result["client_id"] is not None
    assert len(result["client_id"]) > 10


@pytest.mark.asyncio
async def test_onboarding_summary_format():
    from runtime.onboarding.handler import handle_onboarding

    mock_sb = _mock_supabase_onboarding()
    mock_state = AsyncMock(return_value={"mood": "neutral"})

    with patch("runtime.onboarding.handler.supabase", mock_sb), \
         patch("runtime.onboarding.handler._ingest_website", new_callable=AsyncMock, return_value={"chunks_inserted": 0}), \
         patch("runtime.onboarding.handler._generate_soul_prompt", new_callable=AsyncMock, return_value=""), \
         patch("runtime.onboarding.handler._create_character_state", mock_state), \
         patch("runtime.onboarding.handler._save_onboarding_progress", new_callable=AsyncMock):
        result = await handle_onboarding(_base_task())

    assert "DRAFT" in result["summary"]
    assert "Confeitaria Maria" in result["summary"]
    assert "/onboarding/approve/" in result["summary"]
