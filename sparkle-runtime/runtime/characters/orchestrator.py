"""
Character Orchestrator — B2-02.

5th agent type: manages character mood transitions, decides when characters
react to events, and orchestrates "reveal moments" (narrative beats).

This module is purely deterministic — NO LLM calls.  It uses heuristics
and rules to compute mood/energy shifts, detect reveal moments, and build
rich context for the downstream response generator.

Functions:
    evaluate_event       — Given an event, compute character reaction
    get_character_context — Build enriched context for response generation
    process_character_turn — Full turn: load state -> context -> mood -> reaction
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from runtime.db import supabase
from runtime.characters.state import (
    get_character_state,
    update_character_state,
    record_character_event,
)

logger = logging.getLogger(__name__)

# ── Event configuration tables ────────────────────────────────────────────

# mood_effect: target mood after this event (may be overridden by current state)
# energy_delta: added to current energy
# reveal_weight: base probability (0-1) that this event triggers a reveal moment
EVENT_RULES: dict[str, dict[str, Any]] = {
    "conversation_start": {
        "mood_effect": None,          # no forced mood change
        "energy_delta": +0.05,
        "reveal_weight": 0.05,
        "reaction_style": "welcoming",
        "narrative_template": "A new conversation begins.",
    },
    "conversation_end": {
        "mood_effect": None,
        "energy_delta": -0.03,
        "reveal_weight": 0.02,
        "reaction_style": "reflective",
        "narrative_template": "The conversation draws to a close.",
    },
    "positive_feedback": {
        "mood_effect": "happy",
        "energy_delta": +0.10,
        "reveal_weight": 0.15,
        "reaction_style": "grateful",
        "narrative_template": "Positive energy flows in — the character feels seen.",
    },
    "negative_feedback": {
        "mood_effect": "concerned",
        "energy_delta": -0.08,
        "reveal_weight": 0.10,
        "reaction_style": "empathetic",
        "narrative_template": "A moment of tension — the character absorbs the feedback.",
    },
    "milestone": {
        "mood_effect": "excited",
        "energy_delta": +0.15,
        "reveal_weight": 0.60,
        "reaction_style": "celebratory",
        "narrative_template": "A milestone reached — this moment deserves to be marked.",
    },
    "time_passage": {
        "mood_effect": None,           # handled by decay logic
        "energy_delta": 0.0,           # handled by recovery logic
        "reveal_weight": 0.01,
        "reaction_style": "contemplative",
        "narrative_template": "Time passes; the character reflects.",
    },
    "lore_trigger": {
        "mood_effect": "mysterious",
        "energy_delta": +0.05,
        "reveal_weight": 0.75,
        "reaction_style": "storytelling",
        "narrative_template": "Something from the past resurfaces — a thread of lore awakens.",
    },
}

# Mood normalization: extreme moods decay toward neutral over time_passage events
MOOD_DECAY_MAP: dict[str, str] = {
    "excited": "happy",
    "happy": "content",
    "content": "neutral",
    "curious": "content",      # Juno's default — decays gently
    "concerned": "neutral",
    "melancholic": "neutral",
    "mysterious": "neutral",
    "angry": "concerned",
}

# Moods that count as "positive" for context decisions
POSITIVE_MOODS = {"happy", "excited", "content", "curious", "grateful", "celebratory"}
NEGATIVE_MOODS = {"concerned", "melancholic", "angry", "frustrated"}

# Energy baseline: time_passage pushes energy toward this value
ENERGY_BASELINE = 0.75
ENERGY_RECOVERY_RATE = 0.05  # per time_passage tick (30 min)

# Time-of-day personality adjustments (hour in UTC-3 / Sao Paulo)
# Returns (energy_modifier, reaction_style_hint)
def _time_of_day_adjustments() -> tuple[float, str]:
    """Return energy modifier and style hint based on current hour (Sao Paulo)."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    hour = now.hour

    if 6 <= hour < 10:
        return +0.05, "energetic"     # morning boost
    elif 10 <= hour < 14:
        return 0.0, "focused"         # productive hours
    elif 14 <= hour < 18:
        return -0.02, "steady"        # afternoon plateau
    elif 18 <= hour < 22:
        return -0.03, "winding_down"  # evening cooldown
    else:
        return -0.05, "reflective"    # night — introspective


# ── Public API ────────────────────────────────────────────────────────────

async def evaluate_event(
    character_slug: str,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Given an event, decide how the character should react.

    Steps:
      1. Load current state
      2. Look up event rules
      3. Calculate mood shift (event rule + current mood interaction)
      4. Calculate energy delta (event rule + time-of-day)
      5. Determine if this is a reveal moment
      6. Persist state changes via record_character_event

    Returns:
        {
            "mood_effect": str | None,
            "energy_delta": float,
            "reaction": str,           # reaction style for response generator
            "is_reveal_moment": bool,
            "narrative_note": str,
            "previous_mood": str,
            "new_mood": str,
            "new_energy": float,
        }
    """
    event_data = event_data or {}
    rules = EVENT_RULES.get(event_type)
    if rules is None:
        logger.warning("Unknown event type '%s' for character '%s'", event_type, character_slug)
        rules = {
            "mood_effect": None,
            "energy_delta": 0.0,
            "reveal_weight": 0.05,
            "reaction_style": "neutral",
            "narrative_template": f"An unrecognized event occurred: {event_type}.",
        }

    current_state = await get_character_state(character_slug)
    current_mood: str = current_state.get("mood", "neutral")
    current_energy: float = float(current_state.get("energy", 0.75))

    # ── Mood computation ──
    mood_effect = _compute_mood(event_type, rules, current_mood, event_data)
    previous_mood = current_mood

    # ── Energy computation ──
    tod_modifier, tod_style = _time_of_day_adjustments()
    base_delta: float = float(rules.get("energy_delta", 0.0))

    if event_type == "time_passage":
        # Energy recovery toward baseline
        if current_energy < ENERGY_BASELINE:
            energy_delta = min(ENERGY_RECOVERY_RATE, ENERGY_BASELINE - current_energy)
        elif current_energy > ENERGY_BASELINE:
            energy_delta = max(-ENERGY_RECOVERY_RATE, ENERGY_BASELINE - current_energy)
        else:
            energy_delta = 0.0
    else:
        energy_delta = base_delta + tod_modifier

    new_energy = max(0.0, min(0.99, current_energy + energy_delta))

    # ── Reveal moment detection ──
    reveal_weight: float = float(rules.get("reveal_weight", 0.0))
    is_reveal_moment = _check_reveal_moment(
        reveal_weight, current_mood, mood_effect, current_energy, event_data,
    )

    # ── Reaction style ──
    reaction = _pick_reaction_style(rules, tod_style, is_reveal_moment, mood_effect)

    # ── Narrative note ──
    narrative = rules.get("narrative_template", "")
    if is_reveal_moment:
        narrative = f"[REVEAL] {narrative}"
    if event_data.get("detail"):
        narrative += f" ({event_data['detail']})"

    # ── Persist changes ──
    await record_character_event(
        slug=character_slug,
        event=event_type,
        mood_effect=mood_effect,
        energy_delta=energy_delta,
    )

    new_state = await get_character_state(character_slug)
    new_mood = new_state.get("mood", mood_effect or current_mood)

    logger.info(
        "Character '%s' event '%s': mood %s->%s, energy %.2f->%.2f, reveal=%s",
        character_slug, event_type, previous_mood, new_mood,
        current_energy, new_energy, is_reveal_moment,
    )

    return {
        "mood_effect": mood_effect,
        "energy_delta": round(energy_delta, 3),
        "reaction": reaction,
        "is_reveal_moment": is_reveal_moment,
        "narrative_note": narrative,
        "previous_mood": previous_mood,
        "new_mood": new_mood,
        "new_energy": round(new_energy, 2),
    }


async def get_character_context(character_slug: str) -> dict[str, Any]:
    """
    Build rich context for response generation.

    Includes:
      - Current state (mood, energy)
      - Recent events (last 5 from character_conversations)
      - Active arc position
      - Time-of-day personality adjustments
      - Reaction style hints

    Returns:
        Dict ready to be consumed by the response generator / handler.
    """
    state = await get_character_state(character_slug)

    current_mood: str = state.get("mood", "neutral")
    current_energy: float = float(state.get("energy", 0.75))
    arc_position: dict = state.get("arc_position") or {}
    personality_traits: dict = state.get("personality_traits") or {}
    session_context: dict = state.get("session_context") or {}
    last_event: str | None = state.get("last_event")
    last_event_at: str | None = state.get("last_event_at")

    # Recent events from character_conversations (last 5 messages by this character)
    recent_events = await _get_recent_events(character_slug, limit=5)

    # Time-of-day adjustments
    tod_modifier, tod_style = _time_of_day_adjustments()
    effective_energy = max(0.0, min(0.99, current_energy + tod_modifier))

    # Energy band for response tone
    if effective_energy >= 0.80:
        energy_band = "high"
    elif effective_energy >= 0.50:
        energy_band = "moderate"
    elif effective_energy >= 0.25:
        energy_band = "low"
    else:
        energy_band = "depleted"

    # Mood-based response hints
    response_hints = _mood_to_response_hints(current_mood, energy_band)

    return {
        "character_slug": character_slug,
        "mood": current_mood,
        "energy": round(effective_energy, 2),
        "energy_band": energy_band,
        "arc_position": arc_position,
        "personality_traits": personality_traits,
        "session_context": session_context,
        "last_event": last_event,
        "last_event_at": last_event_at,
        "recent_events": recent_events,
        "time_of_day_style": tod_style,
        "response_hints": response_hints,
    }


async def process_character_turn(
    character_slug: str,
    user_message: str,
    channel: str = "whatsapp",
) -> dict[str, Any]:
    """
    Full turn processing for a character interaction.

    Steps:
      1. Load state
      2. Evaluate conversation_start (if first recent message) or ongoing
      3. Detect sentiment heuristics from user_message
      4. Build enriched context for response generation
      5. Return context dict that the handler can merge into prompt

    This does NOT call the LLM — it prepares the enriched context that
    the handler (handler.py) will use when invoking the agent.

    Returns:
        {
            "context": dict,           # from get_character_context
            "event_result": dict | None, # from evaluate_event if triggered
            "system_prompt_additions": str,  # extra prompt text for response gen
        }
    """
    state = await get_character_state(character_slug)

    # Determine if this looks like a new conversation or continuation
    last_event_at = state.get("last_event_at")
    is_new_conversation = _is_new_conversation(last_event_at)

    # Evaluate conversation_start if new
    event_result: dict[str, Any] | None = None
    if is_new_conversation:
        event_result = await evaluate_event(
            character_slug, "conversation_start", {"channel": channel}
        )

    # Detect simple sentiment from user message (heuristic, no LLM)
    detected_event = _detect_message_event(user_message)
    if detected_event:
        event_result = await evaluate_event(
            character_slug, detected_event, {"user_message": user_message}
        )

    # Build context
    context = await get_character_context(character_slug)

    # Build system prompt additions based on orchestrator decisions
    prompt_additions = _build_prompt_additions(context, event_result)

    return {
        "context": context,
        "event_result": event_result,
        "system_prompt_additions": prompt_additions,
    }


# ── Internal helpers ──────────────────────────────────────────────────────

def _compute_mood(
    event_type: str,
    rules: dict[str, Any],
    current_mood: str,
    event_data: dict[str, Any],
) -> str | None:
    """Determine the new mood based on event rules and current state."""
    if event_type == "time_passage":
        # Decay extreme moods toward neutral
        return MOOD_DECAY_MAP.get(current_mood)  # None if already neutral

    target_mood = rules.get("mood_effect")
    if target_mood is None:
        return None

    # If event_data forces a specific mood, use it
    if event_data.get("force_mood"):
        return event_data["force_mood"]

    # If character is already in a positive mood and event is positive, amplify
    if current_mood in POSITIVE_MOODS and target_mood in POSITIVE_MOODS:
        if target_mood == "happy" and current_mood == "happy":
            return "excited"  # amplify

    # If character is in negative mood and gets positive event, moderate
    if current_mood in NEGATIVE_MOODS and target_mood in POSITIVE_MOODS:
        return "neutral"  # tempered recovery, not instant happiness

    return target_mood


def _check_reveal_moment(
    base_weight: float,
    current_mood: str,
    new_mood: str | None,
    current_energy: float,
    event_data: dict[str, Any],
) -> bool:
    """
    Determine if an event qualifies as a 'reveal moment'.

    A reveal moment is a narrative beat worth highlighting — the character
    says or does something that feels significant to the story.

    Factors that increase reveal probability:
      - Base weight from event type
      - Mood transitions (any change)
      - High energy (above 0.85)
      - Explicit flag in event_data
      - Milestone counters

    Returns True/False deterministically based on threshold crossing.
    """
    # Explicit override
    if event_data.get("force_reveal"):
        return True

    score = base_weight

    # Mood transition bonus
    if new_mood is not None and new_mood != current_mood:
        score += 0.15

    # High energy bonus
    if current_energy >= 0.85:
        score += 0.10

    # Milestone data bonus
    if event_data.get("milestone_count"):
        count = int(event_data["milestone_count"])
        if count % 100 == 0:
            score += 0.30
        elif count % 50 == 0:
            score += 0.15
        elif count % 10 == 0:
            score += 0.05

    # Lore connection bonus
    if event_data.get("lore_connection"):
        score += 0.20

    # Deterministic threshold: reveal if score >= 0.50
    return score >= 0.50


def _pick_reaction_style(
    rules: dict[str, Any],
    tod_style: str,
    is_reveal: bool,
    mood_effect: str | None,
) -> str:
    """Pick the reaction style for the response generator."""
    if is_reveal:
        return "storytelling"

    base_style: str = rules.get("reaction_style", "neutral")

    # Mood-specific overrides
    if mood_effect == "excited":
        return "enthusiastic"
    if mood_effect == "mysterious":
        return "storytelling"
    if mood_effect == "concerned":
        return "empathetic"

    # Time-of-day influence (only if base style is generic)
    if base_style == "neutral" and tod_style == "reflective":
        return "reflective"

    return base_style


def _mood_to_response_hints(mood: str, energy_band: str) -> dict[str, str]:
    """Map mood + energy to concrete hints for the response generator."""
    hints: dict[str, str] = {}

    # Tone
    tone_map = {
        "neutral": "calm and balanced",
        "happy": "warm and upbeat",
        "excited": "enthusiastic and energetic",
        "content": "serene and positive",
        "concerned": "gentle and caring",
        "melancholic": "soft and thoughtful",
        "mysterious": "intriguing and allusive",
        "angry": "firm but controlled",
    }
    hints["tone"] = tone_map.get(mood, "neutral and measured")

    # Verbosity based on energy
    verbosity_map = {
        "high": "expressive, can use longer responses",
        "moderate": "balanced, normal response length",
        "low": "concise, shorter responses",
        "depleted": "minimal, very brief responses",
    }
    hints["verbosity"] = verbosity_map.get(energy_band, "balanced")

    # Emoji/expressiveness
    if mood in POSITIVE_MOODS and energy_band in ("high", "moderate"):
        hints["expressiveness"] = "can use occasional expressive punctuation"
    elif mood in NEGATIVE_MOODS:
        hints["expressiveness"] = "restrained, measured expression"
    else:
        hints["expressiveness"] = "neutral expression"

    return hints


def _is_new_conversation(last_event_at: str | None) -> bool:
    """Determine if this is a new conversation based on last event timestamp."""
    if last_event_at is None:
        return True

    try:
        last_dt = datetime.fromisoformat(last_event_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        gap = (now - last_dt).total_seconds()
        # More than 30 minutes since last event = new conversation
        return gap > 1800
    except (ValueError, TypeError):
        return True


def _detect_message_event(message: str) -> str | None:
    """
    Simple heuristic to detect event types from user message text.

    Returns event_type string or None if no event detected.
    No LLM — pure keyword matching.
    """
    msg_lower = message.lower().strip()

    # Positive feedback signals
    positive_keywords = [
        "obrigado", "obrigada", "valeu", "perfeito", "maravilhoso",
        "excelente", "adorei", "amei", "incrivel", "incrível",
        "top", "show", "parabens", "parabéns", "muito bom",
        "thank", "thanks", "great", "awesome", "perfect", "love it",
        "amazing", "excellent", "wonderful",
    ]
    if any(kw in msg_lower for kw in positive_keywords):
        return "positive_feedback"

    # Negative feedback signals
    negative_keywords = [
        "ruim", "horrivel", "horrível", "péssimo", "pessimo",
        "errado", "bug", "problema", "não funciona", "não gostei",
        "decepcionado", "decepcionada", "frustrado", "frustrada",
        "bad", "terrible", "wrong", "broken", "hate", "disappointed",
        "frustrated", "angry",
    ]
    if any(kw in msg_lower for kw in negative_keywords):
        return "negative_feedback"

    return None


async def _get_recent_events(character_slug: str, limit: int = 5) -> list[dict[str, Any]]:
    """Fetch recent conversation entries for context building."""
    try:
        # Get character_id from characters table
        char_result = await asyncio.to_thread(
            lambda: supabase.table("characters")
            .select("id")
            .eq("slug", character_slug)
            .maybe_single()
            .execute()
        )
        char_data = char_result.data if char_result else None
        if not char_data:
            return []

        character_id = char_data["id"]

        result = await asyncio.to_thread(
            lambda: supabase.table("character_conversations")
            .select("role, content, channel, created_at")
            .eq("character_id", character_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = result.data or []
        return list(reversed(items))  # chronological order
    except Exception as e:
        logger.warning("Failed to get recent events for '%s': %s", character_slug, e)
        return []


def _build_prompt_additions(
    context: dict[str, Any],
    event_result: dict[str, Any] | None,
) -> str:
    """
    Build additional system prompt text based on orchestrator context.

    This gets appended to the character's soul_prompt to influence
    response generation without LLM calls in the orchestrator itself.
    """
    parts: list[str] = []

    # Mood and energy state
    mood = context.get("mood", "neutral")
    energy_band = context.get("energy_band", "moderate")
    hints = context.get("response_hints", {})

    parts.append(f"[Character State] Mood: {mood} | Energy: {energy_band}")
    if hints.get("tone"):
        parts.append(f"[Tone] {hints['tone']}")
    if hints.get("verbosity"):
        parts.append(f"[Verbosity] {hints['verbosity']}")

    # Time of day influence
    tod = context.get("time_of_day_style", "")
    if tod:
        parts.append(f"[Time-of-day] {tod}")

    # Event-specific additions
    if event_result:
        reaction = event_result.get("reaction", "")
        if reaction:
            parts.append(f"[Reaction style] {reaction}")
        if event_result.get("is_reveal_moment"):
            parts.append("[REVEAL MOMENT] This is a significant narrative beat. "
                         "Share something meaningful about your story or personality.")
        narrative = event_result.get("narrative_note", "")
        if narrative:
            parts.append(f"[Narrative] {narrative}")

    # Arc position hints
    arc = context.get("arc_position", {})
    if arc.get("current_phase"):
        parts.append(f"[Arc] Currently in phase: {arc['current_phase']}")

    return "\n".join(parts)
