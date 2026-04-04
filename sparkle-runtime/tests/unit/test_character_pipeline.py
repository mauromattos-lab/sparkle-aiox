"""
Unit tests for Character Response Pipeline (B2-03).

Tests the 6-phase pipeline: tone selection, system prompt building,
history formatting, and graceful degradation on failures.

All external dependencies (Supabase, Claude API, TTS) are mocked.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Phase 3: Tone selection tests ───────────────────────────────────────────

def test_phase3_select_tone_happy_high():
    from runtime.characters.pipeline import phase_3_select_tone

    result = phase_3_select_tone("happy", "high")
    assert "entusiasmo" in result.lower() or "calor" in result.lower()


def test_phase3_select_tone_all_moods():
    """Verify all mood+energy combinations produce a non-empty directive."""
    from runtime.characters.pipeline import phase_3_select_tone, TONE_DIRECTIVES

    for mood in TONE_DIRECTIVES:
        for energy_band in ("high", "moderate", "low", "depleted"):
            directive = phase_3_select_tone(mood, energy_band)
            assert isinstance(directive, str)
            assert len(directive) > 5, f"Empty directive for ({mood}, {energy_band})"


def test_phase3_select_tone_unknown_mood_fallback():
    from runtime.characters.pipeline import phase_3_select_tone, _DEFAULT_TONE

    result = phase_3_select_tone("nonexistent_mood", "moderate")
    # Should fall back to neutral mood tones or default
    assert isinstance(result, str) and len(result) > 0


def test_phase3_select_tone_unknown_energy_band():
    from runtime.characters.pipeline import phase_3_select_tone, _DEFAULT_TONE

    result = phase_3_select_tone("neutral", "unknown_band")
    assert result == _DEFAULT_TONE


# ── TONE_DIRECTIVES completeness ───────────────────────────────────────────

def test_tone_directives_has_all_moods():
    from runtime.characters.pipeline import TONE_DIRECTIVES

    expected_moods = {"neutral", "happy", "excited", "content", "concerned", "melancholic", "mysterious", "angry"}
    assert expected_moods == set(TONE_DIRECTIVES.keys())


def test_tone_directives_has_all_energy_bands():
    from runtime.characters.pipeline import TONE_DIRECTIVES

    expected_bands = {"high", "moderate", "low", "depleted"}
    for mood, bands in TONE_DIRECTIVES.items():
        assert set(bands.keys()) == expected_bands, f"Mood '{mood}' missing energy bands"


def test_tone_directives_total_combos():
    """32 combinations: 8 moods x 4 energy bands."""
    from runtime.characters.pipeline import TONE_DIRECTIVES

    total = sum(len(bands) for bands in TONE_DIRECTIVES.values())
    assert total == 32


# ── _build_enriched_system_prompt tests ─────────────────────────────────────

def test_build_enriched_prompt_all_parts():
    from runtime.characters.pipeline import _build_enriched_system_prompt

    result = _build_enriched_system_prompt(
        soul_prompt="I am Finch.",
        lore_context="Finch was born in the digital age.",
        system_prompt_additions="[Mood] happy",
        tone_directive="Responda com calor.",
    )
    assert "I am Finch." in result
    assert "digital age" in result
    assert "[Mood] happy" in result
    assert "Responda com calor" in result
    assert "Contexto sobre sua" in result  # lore section header
    assert "Estado atual" in result  # additions section header
    assert "Diretiva de tom" in result  # tone section header


def test_build_enriched_prompt_empty_parts():
    from runtime.characters.pipeline import _build_enriched_system_prompt

    result = _build_enriched_system_prompt(
        soul_prompt="", lore_context="", system_prompt_additions="", tone_directive=""
    )
    assert result == ""


def test_build_enriched_prompt_only_soul():
    from runtime.characters.pipeline import _build_enriched_system_prompt

    result = _build_enriched_system_prompt(
        soul_prompt="Core personality", lore_context="", system_prompt_additions="", tone_directive=""
    )
    assert result == "Core personality"


# ── _format_history tests ───────────────────────────────────────────────────

def test_format_history_empty():
    from runtime.characters.pipeline import _format_history

    assert _format_history([], "Finch") == ""


def test_format_history_basic():
    from runtime.characters.pipeline import _format_history

    history = [
        {"role": "user", "content": "Oi!"},
        {"role": "character", "content": "Ola!"},
    ]
    result = _format_history(history, "Finch")
    assert "Usuário: Oi!" in result
    assert "Finch: Ola!" in result


def test_format_history_uses_character_name():
    from runtime.characters.pipeline import _format_history

    history = [{"role": "character", "content": "Hello"}]
    result = _format_history(history, "Zenya")
    assert "Zenya: Hello" in result


# ── Phase 1: load_state graceful degradation ────────────────────────────────

@pytest.mark.asyncio
async def test_phase1_load_state_success():
    from runtime.characters.pipeline import phase_1_load_state

    state = {"mood": "happy", "energy": 0.80}
    with patch("runtime.characters.pipeline.get_character_state", new_callable=AsyncMock, return_value=state):
        result = await phase_1_load_state("finch")
    assert result["mood"] == "happy"
    assert result["energy"] == 0.80


@pytest.mark.asyncio
async def test_phase1_load_state_fallback_on_error():
    from runtime.characters.pipeline import phase_1_load_state

    with patch("runtime.characters.pipeline.get_character_state", new_callable=AsyncMock, side_effect=Exception("DB down")):
        result = await phase_1_load_state("finch")
    assert result["mood"] == "neutral"
    assert result["energy"] == 0.75


# ── Phase 2: apply_context graceful degradation ────────────────────────────

@pytest.mark.asyncio
async def test_phase2_apply_context_success():
    from runtime.characters.pipeline import phase_2_apply_context

    mock_result = {
        "context": {"mood": "excited", "energy": 0.90, "energy_band": "high"},
        "event_result": None,
        "system_prompt_additions": "[Mood] excited",
    }
    with patch("runtime.characters.orchestrator.process_character_turn", new_callable=AsyncMock, return_value=mock_result):
        result = await phase_2_apply_context("finch", "hello", "whatsapp")
    assert result["context"]["mood"] == "excited"


@pytest.mark.asyncio
async def test_phase2_apply_context_fallback_on_error():
    from runtime.characters.pipeline import phase_2_apply_context

    with patch("runtime.characters.orchestrator.process_character_turn", new_callable=AsyncMock, side_effect=Exception("Orchestrator crash")):
        result = await phase_2_apply_context("finch", "hello", "whatsapp")
    assert result["context"]["mood"] == "neutral"
    assert result["system_prompt_additions"] == ""


# ── Phase 4: generate_response error handling ──────────────────────────────

@pytest.mark.asyncio
async def test_phase4_generate_response_success():
    from runtime.characters.pipeline import phase_4_generate_response

    with patch("runtime.characters.pipeline.call_claude", new_callable=AsyncMock, return_value="Ola! Sou o Finch."):
        result = await phase_4_generate_response("Oi", "System prompt", "claude-haiku-4-5-20251001", "finch")
    assert result == "Ola! Sou o Finch."


@pytest.mark.asyncio
async def test_phase4_generate_response_raises_on_error():
    from runtime.characters.pipeline import phase_4_generate_response
    from fastapi import HTTPException

    with patch("runtime.characters.pipeline.call_claude", new_callable=AsyncMock, side_effect=Exception("API down")):
        with pytest.raises(HTTPException) as exc_info:
            await phase_4_generate_response("Oi", "System", "model", "finch")
    assert exc_info.value.status_code == 500


# ── Phase 5: update_state best-effort ──────────────────────────────────────

@pytest.mark.asyncio
async def test_phase5_update_state_no_crash_on_error():
    from runtime.characters.pipeline import phase_5_update_state

    with patch("runtime.characters.pipeline.record_character_event", new_callable=AsyncMock, side_effect=Exception("DB fail")):
        # Should NOT raise
        await phase_5_update_state("finch", "Oi", "Ola!")


@pytest.mark.asyncio
async def test_phase5_update_state_records_exchange():
    from runtime.characters.pipeline import phase_5_update_state

    mock_record = AsyncMock()
    with patch("runtime.characters.pipeline.record_character_event", mock_record):
        await phase_5_update_state("finch", "Oi", "Ola!")

    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args
    assert call_kwargs.kwargs.get("event") == "conversation_exchange" or \
           call_kwargs[1].get("event") == "conversation_exchange" or \
           "conversation_exchange" in str(call_kwargs)


# ── Phase 6: persist best-effort ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase6_persist_no_crash_on_error():
    from runtime.characters.pipeline import phase_6_persist

    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception("DB fail")

    with patch("runtime.characters.pipeline.supabase", mock_sb):
        # Should NOT raise
        await phase_6_persist(
            character_id="char-001",
            user_identifier="5512999",
            channel="whatsapp",
            user_message="Oi",
            character_response="Ola!",
        )
