"""
Unit tests for Character Orchestrator (B2-02).

Tests event evaluation, mood transitions, time-of-day adjustments,
reveal moment detection, and prompt building helpers.

All DB calls (get_character_state, record_character_event) are mocked.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _default_state(**overrides):
    """Build a default character state dict."""
    state = {
        "mood": "neutral",
        "energy": 0.75,
        "arc_position": {},
        "personality_traits": {},
        "session_context": {},
        "last_event": None,
        "last_event_at": None,
    }
    state.update(overrides)
    return state


# ── EVENT_RULES constant tests ──────────────────────────────────────────────

def test_event_rules_has_required_events():
    from runtime.characters.orchestrator import EVENT_RULES

    required = [
        "conversation_start", "conversation_end", "positive_feedback",
        "negative_feedback", "milestone", "time_passage", "lore_trigger",
    ]
    for event_type in required:
        assert event_type in EVENT_RULES, f"Missing event type '{event_type}'"


def test_event_rules_structure():
    from runtime.characters.orchestrator import EVENT_RULES

    required_keys = {"mood_effect", "energy_delta", "reveal_weight", "reaction_style", "narrative_template"}
    for name, rules in EVENT_RULES.items():
        for key in required_keys:
            assert key in rules, f"Event '{name}' missing key '{key}'"


# ── _compute_mood tests ─────────────────────────────────────────────────────

def test_compute_mood_time_passage_decay():
    from runtime.characters.orchestrator import _compute_mood

    rules = {"mood_effect": None, "energy_delta": 0.0}
    # excited -> happy via MOOD_DECAY_MAP
    result = _compute_mood("time_passage", rules, "excited", {})
    assert result == "happy"


def test_compute_mood_time_passage_neutral_stays_none():
    from runtime.characters.orchestrator import _compute_mood

    rules = {"mood_effect": None}
    result = _compute_mood("time_passage", rules, "neutral", {})
    assert result is None


def test_compute_mood_force_mood_override():
    from runtime.characters.orchestrator import _compute_mood

    rules = {"mood_effect": "happy"}
    result = _compute_mood("positive_feedback", rules, "neutral", {"force_mood": "excited"})
    assert result == "excited"


def test_compute_mood_positive_amplification():
    from runtime.characters.orchestrator import _compute_mood

    rules = {"mood_effect": "happy"}
    # happy + happy event -> excited
    result = _compute_mood("positive_feedback", rules, "happy", {})
    assert result == "excited"


def test_compute_mood_negative_to_positive_tempers():
    from runtime.characters.orchestrator import _compute_mood

    rules = {"mood_effect": "happy"}
    # concerned + happy event -> neutral (tempered)
    result = _compute_mood("positive_feedback", rules, "concerned", {})
    assert result == "neutral"


def test_compute_mood_none_when_no_effect():
    from runtime.characters.orchestrator import _compute_mood

    rules = {"mood_effect": None}
    result = _compute_mood("conversation_start", rules, "neutral", {})
    assert result is None


# ── _check_reveal_moment tests ──────────────────────────────────────────────

def test_reveal_moment_force_flag():
    from runtime.characters.orchestrator import _check_reveal_moment

    result = _check_reveal_moment(0.0, "neutral", None, 0.5, {"force_reveal": True})
    assert result is True


def test_reveal_moment_high_weight_with_mood_change():
    from runtime.characters.orchestrator import _check_reveal_moment

    # lore_trigger has weight 0.75, mood change adds 0.15 => 0.90 >= 0.50
    result = _check_reveal_moment(0.75, "neutral", "mysterious", 0.5, {})
    assert result is True


def test_reveal_moment_low_weight_no_triggers():
    from runtime.characters.orchestrator import _check_reveal_moment

    result = _check_reveal_moment(0.05, "neutral", None, 0.5, {})
    assert result is False


def test_reveal_moment_high_energy_bonus():
    from runtime.characters.orchestrator import _check_reveal_moment

    # base 0.35 + mood_change 0.15 + high_energy 0.10 = 0.60 >= 0.50
    result = _check_reveal_moment(0.35, "neutral", "happy", 0.90, {})
    assert result is True


def test_reveal_moment_milestone_100_bonus():
    from runtime.characters.orchestrator import _check_reveal_moment

    # base 0.15 + milestone_100 bonus 0.30 = 0.45 < 0.50 — not quite
    result = _check_reveal_moment(0.15, "neutral", None, 0.5, {"milestone_count": 100})
    assert result is False  # 0.15 + 0.30 = 0.45

    # base 0.20 + milestone_100 bonus 0.30 = 0.50 >= 0.50
    result = _check_reveal_moment(0.20, "neutral", None, 0.5, {"milestone_count": 100})
    assert result is True


def test_reveal_moment_lore_connection_bonus():
    from runtime.characters.orchestrator import _check_reveal_moment

    # base 0.15 + lore 0.20 + mood_change 0.15 = 0.50 >= 0.50
    result = _check_reveal_moment(0.15, "neutral", "happy", 0.5, {"lore_connection": True})
    assert result is True


# ── _pick_reaction_style tests ──────────────────────────────────────────────

def test_pick_reaction_reveal_always_storytelling():
    from runtime.characters.orchestrator import _pick_reaction_style

    result = _pick_reaction_style({"reaction_style": "welcoming"}, "focused", True, None)
    assert result == "storytelling"


def test_pick_reaction_excited_mood():
    from runtime.characters.orchestrator import _pick_reaction_style

    result = _pick_reaction_style({"reaction_style": "welcoming"}, "focused", False, "excited")
    assert result == "enthusiastic"


def test_pick_reaction_mysterious_mood():
    from runtime.characters.orchestrator import _pick_reaction_style

    result = _pick_reaction_style({"reaction_style": "welcoming"}, "focused", False, "mysterious")
    assert result == "storytelling"


def test_pick_reaction_concerned_mood():
    from runtime.characters.orchestrator import _pick_reaction_style

    result = _pick_reaction_style({"reaction_style": "welcoming"}, "focused", False, "concerned")
    assert result == "empathetic"


def test_pick_reaction_tod_influence():
    from runtime.characters.orchestrator import _pick_reaction_style

    result = _pick_reaction_style({"reaction_style": "neutral"}, "reflective", False, None)
    assert result == "reflective"


def test_pick_reaction_base_style_default():
    from runtime.characters.orchestrator import _pick_reaction_style

    result = _pick_reaction_style({"reaction_style": "welcoming"}, "focused", False, None)
    assert result == "welcoming"


# ── _mood_to_response_hints tests ───────────────────────────────────────────

def test_mood_hints_happy_high():
    from runtime.characters.orchestrator import _mood_to_response_hints

    hints = _mood_to_response_hints("happy", "high")
    assert "warm" in hints["tone"].lower() or "upbeat" in hints["tone"].lower()
    assert "expressive" in hints["verbosity"].lower() or "longer" in hints["verbosity"].lower()
    assert "expressive" in hints["expressiveness"].lower()


def test_mood_hints_concerned():
    from runtime.characters.orchestrator import _mood_to_response_hints

    hints = _mood_to_response_hints("concerned", "moderate")
    assert "caring" in hints["tone"].lower() or "gentle" in hints["tone"].lower()
    assert "restrained" in hints["expressiveness"].lower()


def test_mood_hints_depleted():
    from runtime.characters.orchestrator import _mood_to_response_hints

    hints = _mood_to_response_hints("neutral", "depleted")
    assert "minimal" in hints["verbosity"].lower() or "brief" in hints["verbosity"].lower()


# ── _is_new_conversation tests ──────────────────────────────────────────────

def test_is_new_conversation_none():
    from runtime.characters.orchestrator import _is_new_conversation

    assert _is_new_conversation(None) is True


def test_is_new_conversation_old_timestamp():
    from runtime.characters.orchestrator import _is_new_conversation

    assert _is_new_conversation("2020-01-01T00:00:00+00:00") is True


def test_is_new_conversation_recent_timestamp():
    from runtime.characters.orchestrator import _is_new_conversation
    from datetime import datetime, timezone, timedelta

    # 5 minutes ago => not new
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert _is_new_conversation(recent) is False


def test_is_new_conversation_invalid_timestamp():
    from runtime.characters.orchestrator import _is_new_conversation

    assert _is_new_conversation("not-a-date") is True


# ── _detect_message_event tests ─────────────────────────────────────────────

def test_detect_positive_feedback_pt():
    from runtime.characters.orchestrator import _detect_message_event

    assert _detect_message_event("Obrigado pelo atendimento!") == "positive_feedback"
    assert _detect_message_event("Perfeito, era isso mesmo") == "positive_feedback"
    assert _detect_message_event("valeu demais") == "positive_feedback"


def test_detect_negative_feedback_pt():
    from runtime.characters.orchestrator import _detect_message_event

    assert _detect_message_event("Isso está errado") == "negative_feedback"
    assert _detect_message_event("tem um bug aqui") == "negative_feedback"
    assert _detect_message_event("não funciona nada") == "negative_feedback"


def test_detect_no_event():
    from runtime.characters.orchestrator import _detect_message_event

    assert _detect_message_event("qual o horário de funcionamento?") is None
    assert _detect_message_event("me manda o cardápio") is None


def test_detect_positive_feedback_en():
    from runtime.characters.orchestrator import _detect_message_event

    assert _detect_message_event("thanks a lot!") == "positive_feedback"
    assert _detect_message_event("this is awesome") == "positive_feedback"


def test_detect_negative_feedback_en():
    from runtime.characters.orchestrator import _detect_message_event

    assert _detect_message_event("this is terrible") == "negative_feedback"
    assert _detect_message_event("I'm so frustrated") == "negative_feedback"


# ── _build_prompt_additions tests ───────────────────────────────────────────

def test_build_prompt_additions_basic():
    from runtime.characters.orchestrator import _build_prompt_additions

    context = {
        "mood": "happy",
        "energy_band": "high",
        "response_hints": {"tone": "warm", "verbosity": "expressive"},
        "time_of_day_style": "focused",
    }
    result = _build_prompt_additions(context, None)
    assert "[Character State]" in result
    assert "happy" in result
    assert "[Tone]" in result


def test_build_prompt_additions_with_event():
    from runtime.characters.orchestrator import _build_prompt_additions

    context = {
        "mood": "neutral",
        "energy_band": "moderate",
        "response_hints": {},
        "time_of_day_style": "",
    }
    event_result = {
        "reaction": "storytelling",
        "is_reveal_moment": True,
        "narrative_note": "A milestone!",
    }
    result = _build_prompt_additions(context, event_result)
    assert "[REVEAL MOMENT]" in result
    assert "storytelling" in result
    assert "milestone" in result


def test_build_prompt_additions_arc_position():
    from runtime.characters.orchestrator import _build_prompt_additions

    context = {
        "mood": "neutral",
        "energy_band": "moderate",
        "response_hints": {},
        "time_of_day_style": "",
        "arc_position": {"current_phase": "introduction"},
    }
    result = _build_prompt_additions(context, None)
    assert "introduction" in result


# ── evaluate_event integration test ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_event_positive_feedback():
    """End-to-end test for evaluate_event with mocked DB."""
    from runtime.characters.orchestrator import evaluate_event

    state = _default_state(mood="neutral", energy=0.70)

    with patch("runtime.characters.orchestrator.get_character_state", new_callable=AsyncMock, return_value=state), \
         patch("runtime.characters.orchestrator.record_character_event", new_callable=AsyncMock), \
         patch("runtime.characters.orchestrator._time_of_day_adjustments", return_value=(0.0, "focused")):
        result = await evaluate_event("finch", "positive_feedback", {})

    assert result["previous_mood"] == "neutral"
    assert result["mood_effect"] == "happy"
    assert result["energy_delta"] > 0  # positive_feedback has +0.10


@pytest.mark.asyncio
async def test_evaluate_event_unknown_type():
    """Unknown event types should get default rules and not crash."""
    from runtime.characters.orchestrator import evaluate_event

    state = _default_state()

    with patch("runtime.characters.orchestrator.get_character_state", new_callable=AsyncMock, return_value=state), \
         patch("runtime.characters.orchestrator.record_character_event", new_callable=AsyncMock), \
         patch("runtime.characters.orchestrator._time_of_day_adjustments", return_value=(0.0, "focused")):
        result = await evaluate_event("finch", "completely_unknown_event", {})

    assert result["mood_effect"] is None
    assert "reaction" in result


@pytest.mark.asyncio
async def test_evaluate_event_time_passage_energy_recovery():
    """time_passage should push energy toward baseline."""
    from runtime.characters.orchestrator import evaluate_event, ENERGY_BASELINE

    state = _default_state(energy=0.50)

    with patch("runtime.characters.orchestrator.get_character_state", new_callable=AsyncMock, return_value=state), \
         patch("runtime.characters.orchestrator.record_character_event", new_callable=AsyncMock), \
         patch("runtime.characters.orchestrator._time_of_day_adjustments", return_value=(0.0, "focused")):
        result = await evaluate_event("finch", "time_passage", {})

    assert result["energy_delta"] > 0  # recovering toward 0.75


@pytest.mark.asyncio
async def test_evaluate_event_reveal_moment_with_lore():
    """lore_trigger with lore_connection data should produce reveal moment."""
    from runtime.characters.orchestrator import evaluate_event

    state = _default_state(mood="neutral", energy=0.70)

    with patch("runtime.characters.orchestrator.get_character_state", new_callable=AsyncMock, return_value=state), \
         patch("runtime.characters.orchestrator.record_character_event", new_callable=AsyncMock), \
         patch("runtime.characters.orchestrator._time_of_day_adjustments", return_value=(0.0, "focused")):
        result = await evaluate_event("finch", "lore_trigger", {"lore_connection": True})

    assert result["is_reveal_moment"] is True
    assert "[REVEAL]" in result["narrative_note"]


# ── MOOD_DECAY_MAP completeness ─────────────────────────────────────────────

def test_mood_decay_map_values():
    from runtime.characters.orchestrator import MOOD_DECAY_MAP

    # Verify known decays
    assert MOOD_DECAY_MAP["excited"] == "happy"
    assert MOOD_DECAY_MAP["happy"] == "content"
    assert MOOD_DECAY_MAP["content"] == "neutral"
    assert MOOD_DECAY_MAP["angry"] == "concerned"
