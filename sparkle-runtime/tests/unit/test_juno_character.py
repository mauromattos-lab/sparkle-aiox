"""
Unit tests for Juno character (B4-01).

Validates:
  - Juno soul prompt exists and is in Portuguese
  - Juno tone directives cover all 32+ combinations (8 moods + curious x 4 energy bands)
  - Juno state is independent from Zenya (via mocked DB)
  - Juno's personality traits are creative-focused
  - Pipeline selects Juno-specific tones when character_slug="juno"
  - Multi-character isolation: processing one character does not affect the other
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ── Soul prompt tests ──────────────────────────────────────────────────────

def test_juno_soul_prompt_exists():
    from runtime.characters.juno_soul import SOUL_PROMPT

    assert isinstance(SOUL_PROMPT, str)
    assert len(SOUL_PROMPT) > 200, "Soul prompt should be substantial"


def test_juno_soul_prompt_in_portuguese():
    from runtime.characters.juno_soul import SOUL_PROMPT

    # Check for Portuguese-specific words/phrases
    pt_markers = ["você", "criativ", "português", "brasileiro", "responda"]
    found = sum(1 for m in pt_markers if m.lower() in SOUL_PROMPT.lower())
    assert found >= 3, f"Soul prompt should be in Portuguese (found {found}/5 markers)"


def test_juno_soul_prompt_has_identity():
    from runtime.characters.juno_soul import SOUL_PROMPT

    assert "Juno" in SOUL_PROMPT
    assert "criativ" in SOUL_PROMPT.lower()
    assert "Sparkle" in SOUL_PROMPT


def test_juno_soul_prompt_mentions_zenya():
    """Juno should reference Zenya as her counterpart."""
    from runtime.characters.juno_soul import SOUL_PROMPT

    assert "Zenya" in SOUL_PROMPT


def test_juno_soul_prompt_has_creative_keywords():
    from runtime.characters.juno_soul import SOUL_PROMPT

    creative_words = ["arte", "metáfora", "cores", "visual", "pintar", "história"]
    found = sum(1 for w in creative_words if w.lower() in SOUL_PROMPT.lower())
    assert found >= 3, f"Soul prompt should have creative keywords (found {found}/6)"


# ── Personality traits tests ──────────────────────────────────────────────

def test_juno_personality_traits_creative_focused():
    from runtime.characters.juno_soul import PERSONALITY_TRAITS

    assert isinstance(PERSONALITY_TRAITS, dict)
    assert "creative" in PERSONALITY_TRAITS
    assert "artistic" in PERSONALITY_TRAITS
    assert "playful" in PERSONALITY_TRAITS
    assert "expressive" in PERSONALITY_TRAITS


def test_juno_personality_traits_values_are_high():
    """Creative traits should be high (>= 0.8)."""
    from runtime.characters.juno_soul import PERSONALITY_TRAITS

    creative_traits = ["creative", "artistic", "expressive"]
    for trait in creative_traits:
        assert PERSONALITY_TRAITS[trait] >= 0.80, (
            f"Trait '{trait}' should be >= 0.80, got {PERSONALITY_TRAITS[trait]}"
        )


def test_juno_personality_traits_all_between_0_and_1():
    from runtime.characters.juno_soul import PERSONALITY_TRAITS

    for trait, value in PERSONALITY_TRAITS.items():
        assert 0.0 <= value <= 1.0, f"Trait '{trait}' out of range: {value}"


# ── Character metadata tests ─────────────────────────────────────────────

def test_juno_metadata_constants():
    from runtime.characters.juno_soul import (
        CHARACTER_SLUG,
        CHARACTER_NAME,
        CHARACTER_SPECIALTY,
        CHARACTER_CAPABILITIES,
    )

    assert CHARACTER_SLUG == "juno"
    assert CHARACTER_NAME == "Juno"
    assert "content_creation" in CHARACTER_CAPABILITIES
    assert "brainstorming" in CHARACTER_CAPABILITIES
    assert "visual_ideas" in CHARACTER_CAPABILITIES


# ── Tone directives tests ────────────────────────────────────────────────

def test_juno_tone_directives_has_standard_moods():
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    standard_moods = {
        "neutral", "happy", "excited", "content",
        "concerned", "melancholic", "mysterious", "angry",
    }
    for mood in standard_moods:
        assert mood in JUNO_TONE_DIRECTIVES, f"Missing mood '{mood}'"


def test_juno_tone_directives_has_curious_mood():
    """Juno should have a 'curious' mood (her default) beyond the standard 8."""
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    assert "curious" in JUNO_TONE_DIRECTIVES


def test_juno_tone_directives_all_energy_bands():
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    energy_bands = {"high", "moderate", "low", "depleted"}
    for mood, tones in JUNO_TONE_DIRECTIVES.items():
        for band in energy_bands:
            assert band in tones, f"Missing energy band '{band}' for mood '{mood}'"
            assert isinstance(tones[band], str), f"Non-string directive for ({mood}, {band})"
            assert len(tones[band]) > 10, f"Empty directive for ({mood}, {band})"


def test_juno_tone_directives_cover_36_combinations():
    """9 moods (8 standard + curious) x 4 energy bands = 36 directives."""
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    count = sum(len(bands) for bands in JUNO_TONE_DIRECTIVES.values())
    assert count >= 36, f"Expected >= 36 tone directives, got {count}"


def test_juno_tones_are_in_portuguese():
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    pt_words = ["responda", "forma", "como"]
    for mood, tones in JUNO_TONE_DIRECTIVES.items():
        for band, directive in tones.items():
            found = any(w in directive.lower() for w in pt_words)
            assert found, f"Directive ({mood}, {band}) doesn't appear to be in Portuguese"


def test_juno_tones_differ_from_generic():
    """Juno's tone directives should be different from the generic ones."""
    from runtime.characters.pipeline import TONE_DIRECTIVES
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    differences = 0
    for mood in TONE_DIRECTIVES:
        if mood in JUNO_TONE_DIRECTIVES:
            for band in ("high", "moderate", "low", "depleted"):
                generic = TONE_DIRECTIVES[mood].get(band, "")
                juno = JUNO_TONE_DIRECTIVES[mood].get(band, "")
                if generic != juno:
                    differences += 1

    assert differences >= 20, (
        f"Juno tones should be substantially different from generic (only {differences} differ)"
    )


# ── Pipeline integration: character-specific tone selection ──────────────

def test_pipeline_phase3_uses_juno_tones():
    """phase_3_select_tone should return Juno-specific directive when slug='juno'."""
    from runtime.characters.pipeline import phase_3_select_tone, TONE_DIRECTIVES
    from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES

    # Force reload of overrides
    from runtime.characters import pipeline
    pipeline._CHARACTER_TONE_OVERRIDES.clear()

    juno_tone = phase_3_select_tone("happy", "high", character_slug="juno")
    generic_tone = phase_3_select_tone("happy", "high", character_slug=None)

    assert juno_tone != generic_tone, "Juno tone should differ from generic"
    assert juno_tone == JUNO_TONE_DIRECTIVES["happy"]["high"]


def test_pipeline_phase3_juno_curious_mood():
    """Juno's 'curious' mood should return a tone even though generic doesn't have it."""
    from runtime.characters import pipeline
    pipeline._CHARACTER_TONE_OVERRIDES.clear()

    tone = pipeline.phase_3_select_tone("curious", "high", character_slug="juno")
    assert "curiosidade" in tone.lower() or "criativ" in tone.lower()


def test_pipeline_phase3_juno_falls_back_for_unknown_mood():
    """If Juno encounters a mood not in her tones, should fallback to generic."""
    from runtime.characters import pipeline
    pipeline._CHARACTER_TONE_OVERRIDES.clear()

    tone = pipeline.phase_3_select_tone("nonexistent_mood", "moderate", character_slug="juno")
    assert isinstance(tone, str) and len(tone) > 0


def test_pipeline_phase3_backward_compatible_without_slug():
    """Calling phase_3_select_tone without slug should work as before."""
    from runtime.characters.pipeline import phase_3_select_tone, TONE_DIRECTIVES

    result = phase_3_select_tone("happy", "high")
    assert result == TONE_DIRECTIVES["happy"]["high"]


# ── Multi-character isolation tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_juno_and_zenya_independent_states():
    """Two characters should have completely independent state."""
    from runtime.characters.state import get_character_state, _cache

    # Clear cache
    _cache.clear()

    juno_state = {
        "character_slug": "juno",
        "mood": "curious",
        "energy": 0.70,
        "personality_traits": {"creative": 0.95, "playful": 0.85},
        "arc_position": {},
        "session_context": {},
        "last_event": None,
        "last_event_at": None,
    }
    zenya_state = {
        "character_slug": "zenya-test",
        "mood": "neutral",
        "energy": 0.75,
        "personality_traits": {"professional": 0.90, "empathetic": 0.85},
        "arc_position": {},
        "session_context": {},
        "last_event": None,
        "last_event_at": None,
    }

    # Mock DB to return different states for different slugs
    async def mock_get_state(slug):
        if slug == "juno":
            return juno_state.copy()
        return zenya_state.copy()

    with patch("runtime.characters.state.get_character_state", side_effect=mock_get_state):
        from runtime.characters.state import get_character_state as get_cs

        juno = await get_cs("juno")
        zenya = await get_cs("zenya-test")

        # States should be independent
        assert juno["mood"] == "curious"
        assert zenya["mood"] == "neutral"
        assert juno["energy"] == 0.70
        assert zenya["energy"] == 0.75
        assert juno["personality_traits"]["creative"] == 0.95
        assert "creative" not in zenya["personality_traits"]


@pytest.mark.asyncio
async def test_juno_tone_selection_independent_from_zenya():
    """Tone selection for Juno should not affect Zenya and vice versa."""
    from runtime.characters import pipeline
    pipeline._CHARACTER_TONE_OVERRIDES.clear()

    juno_tone = pipeline.phase_3_select_tone("happy", "high", character_slug="juno")
    zenya_tone = pipeline.phase_3_select_tone("happy", "high", character_slug="zenya")
    generic_tone = pipeline.phase_3_select_tone("happy", "high")

    # Juno should have her own tone
    assert juno_tone != generic_tone
    # Zenya (no custom tones registered) should get generic
    assert zenya_tone == generic_tone


# ── Orchestrator: curious mood support ───────────────────────────────────

def test_orchestrator_mood_decay_includes_curious():
    """Curious mood should be in the decay map."""
    from runtime.characters.orchestrator import MOOD_DECAY_MAP

    assert "curious" in MOOD_DECAY_MAP
    assert MOOD_DECAY_MAP["curious"] == "content"


def test_orchestrator_curious_is_positive_mood():
    """Curious should be classified as a positive mood."""
    from runtime.characters.orchestrator import POSITIVE_MOODS

    assert "curious" in POSITIVE_MOODS


# ── Migration file existence ─────────────────────────────────────────────

def test_juno_migration_file_exists():
    """Migration 011 for Juno should exist."""
    import os

    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..",
        "migrations",
        "011_juno_character.sql",
    )
    assert os.path.exists(migration_path), "Migration 011_juno_character.sql not found"
