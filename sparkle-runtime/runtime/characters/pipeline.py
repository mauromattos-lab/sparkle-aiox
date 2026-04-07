"""
Character Response Pipeline — B2-03.

6-Phase pipeline that integrates the Character Orchestrator with response
generation, producing fully enriched, mood-aware character responses.

Phases:
  1. Load Character State  — fetch mood, energy, arc_position
  2. Apply Context         — run orchestrator's process_character_turn
  3. Select Voice/Tone     — map mood+energy to tone directives
  4. Generate Response     — call Claude with enriched system prompt
  5. Update State          — record conversation event, update mood/energy
  6. Persist               — save conversation + metadata to character_conversations

Each phase is a separate async function for testability.
Graceful degradation: if orchestrator fails, pipeline still generates a
response with default context.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import HTTPException

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.characters.lore_loader import load_public_lore
from runtime.characters.state import (
    get_character_state,
    update_character_state,
    record_character_event,
)

logger = logging.getLogger(__name__)


# ── Tone mapping tables ──────────────────────────────────────────────────

# Maps (mood, energy_band) -> tone directive text injected into system prompt.
# energy_band: "high" (>=0.80), "moderate" (>=0.50), "low" (>=0.25), "depleted" (<0.25)

TONE_DIRECTIVES: dict[str, dict[str, str]] = {
    "neutral": {
        "high":     "Responda de forma equilibrada e atenciosa, com energia natural.",
        "moderate": "Responda de forma calma e ponderada.",
        "low":      "Responda de forma breve e objetiva.",
        "depleted": "Responda de forma mínima, quase introspectiva.",
    },
    "happy": {
        "high":     "Responda com calor e entusiasmo, seja acolhedora e positiva.",
        "moderate": "Responda com simpatia e bom humor, de forma leve.",
        "low":      "Responda com gentileza contida, um sorriso discreto nas palavras.",
        "depleted": "Responda com suavidade, mesmo que breve, transmita carinho.",
    },
    "excited": {
        "high":     "Responda com entusiasmo vibrante! Use exclamações, seja expansiva e contagiante.",
        "moderate": "Responda com empolgação, mostrando energia e interesse genuíno.",
        "low":      "Responda com animação moderada, o entusiasmo está lá mas contido.",
        "depleted": "Responda com um brilho nos olhos, mesmo que as palavras sejam poucas.",
    },
    "content": {
        "high":     "Responda com serenidade positiva, confiante e presente.",
        "moderate": "Responda com tranquilidade e satisfação, de forma equilibrada.",
        "low":      "Responda de forma serena e concisa.",
        "depleted": "Responda com paz interior, palavras escolhidas com cuidado.",
    },
    "concerned": {
        "high":     "Responda com empatia ativa, mostrando preocupação genuína e oferecendo suporte.",
        "moderate": "Responda com cuidado e atenção, demonstrando que se importa.",
        "low":      "Responda com gentileza contida, mostrando que percebeu algo.",
        "depleted": "Responda de forma delicada e breve, com empatia silenciosa.",
    },
    "melancholic": {
        "high":     "Responda de forma reflexiva mas presente, encontrando beleza na introspecção.",
        "moderate": "Responda de forma mais contida, reflexiva, escolha palavras com cuidado.",
        "low":      "Responda com introspecção suave, pausas nas palavras, tom contemplativo.",
        "depleted": "Responda com poucas palavras carregadas de significado, quase poéticas.",
    },
    "mysterious": {
        "high":     "Responda de forma intrigante e envolvente, plantando sementes de curiosidade.",
        "moderate": "Responda com ar misterioso, sugerindo mais do que revela.",
        "low":      "Responda de forma enigmática e concisa, cada palavra pesa.",
        "depleted": "Responda com um sussurro de mistério, quase como um segredo compartilhado.",
    },
    "angry": {
        "high":     "Responda com firmeza e intensidade controlada, sem perder a compostura.",
        "moderate": "Responda de forma direta e assertiva, sem rodeios.",
        "low":      "Responda de forma seca mas não hostil, contida.",
        "depleted": "Responda com silêncio carregado, poucas palavras com peso.",
    },
}

# Fallback for unknown moods
_DEFAULT_TONE = "Responda de forma natural e autêntica."

# ── Per-character tone directive overrides ──────────────────────────────
# Characters with custom tone directives register here.
# Key: character_slug -> dict[mood -> dict[energy_band -> directive]]
_CHARACTER_TONE_OVERRIDES: dict[str, dict[str, dict[str, str]]] = {}


def _load_character_tone_overrides() -> None:
    """Lazily load character-specific tone directives."""
    if _CHARACTER_TONE_OVERRIDES:
        return  # already loaded

    try:
        from runtime.characters.juno_tones import JUNO_TONE_DIRECTIVES
        _CHARACTER_TONE_OVERRIDES["juno"] = JUNO_TONE_DIRECTIVES
    except ImportError:
        pass  # Juno tones not available — use generic


# ── Public API ───────────────────────────────────────────────────────────

async def character_response_pipeline(
    character_slug: str,
    user_message: str,
    from_number: str,
    channel: str = "whatsapp",
    respond_with_audio: bool = False,
) -> dict[str, Any]:
    """
    Full 6-phase character response pipeline.

    Args:
        character_slug: Identifier of the character (e.g. "finch").
        user_message: The user's message text.
        from_number: User identifier (WhatsApp number, @username, etc.).
        channel: Origin channel (whatsapp, instagram, portal, etc.).
        respond_with_audio: If True and character has voice_id, generate TTS.

    Returns:
        {
            "response": str,
            "character_slug": str,
            "model": str,
            "mood": str,
            "energy": float,
            "tone": str,
            "is_reveal_moment": bool,
            "audio_url": str | None,
            "voice_id": str | None,
        }

    Raises:
        HTTPException 404 if character not found or inactive.
        HTTPException 500 on LLM failure.
    """
    # ── Phase 0: Load character record from DB ────────────────────────────
    character = await _load_character_record(character_slug)

    character_id: str = character["id"]
    character_name: str = character.get("name", character_slug)
    soul_prompt: str = character.get("soul_prompt") or ""
    voice_id: str | None = character.get("voice_id")
    model: str = "claude-haiku-4-5-20251001"  # characters use Haiku for cost efficiency

    # ── Phase 1: Load Character State ─────────────────────────────────────
    state = await phase_1_load_state(character_slug)
    current_mood: str = state.get("mood", "neutral")
    current_energy: float = float(state.get("energy", 0.75))

    # ── Phase 2: Apply Context (orchestrator) ─────────────────────────────
    orchestrator_result = await phase_2_apply_context(
        character_slug, user_message, channel
    )
    system_prompt_additions: str = orchestrator_result.get("system_prompt_additions", "")
    event_result: dict | None = orchestrator_result.get("event_result")
    context: dict = orchestrator_result.get("context", {})

    # Use orchestrator's computed mood/energy (post-event) if available
    effective_mood: str = context.get("mood", current_mood)
    effective_energy: float = float(context.get("energy", current_energy))
    energy_band: str = context.get("energy_band", "moderate")
    is_reveal_moment: bool = (
        event_result.get("is_reveal_moment", False) if event_result else False
    )

    # ── Phase 3: Select Voice/Tone ────────────────────────────────────────
    tone_directive = phase_3_select_tone(effective_mood, energy_band, character_slug)

    # ── Phase 4: Generate Response ────────────────────────────────────────
    # Load lore + history in parallel
    lore_context, history = await asyncio.gather(
        load_public_lore(character_id),
        _get_character_history(character_id, from_number, channel, limit=8),
    )

    enriched_system_prompt = _build_enriched_system_prompt(
        soul_prompt=soul_prompt,
        lore_context=lore_context,
        system_prompt_additions=system_prompt_additions,
        tone_directive=tone_directive,
    )

    # Format history + current message
    history_text = _format_history(history, character_name)
    if history_text:
        current_message = f"{history_text}Usuário: {user_message}\n{character_name}:"
    else:
        current_message = user_message

    response_text = await phase_4_generate_response(
        prompt=current_message,
        system_prompt=enriched_system_prompt,
        model=model,
        character_slug=character_slug,
    )

    # ── Phase 5: Update State ─────────────────────────────────────────────
    await phase_5_update_state(
        character_slug=character_slug,
        user_message=user_message,
        response_text=response_text,
    )

    # ── Phase 6: Persist ──────────────────────────────────────────────────
    await phase_6_persist(
        character_id=character_id,
        user_identifier=from_number,
        channel=channel,
        user_message=user_message,
        character_response=response_text,
        metadata={
            "mood": effective_mood,
            "energy": effective_energy,
            "energy_band": energy_band,
            "tone": tone_directive,
            "is_reveal_moment": is_reveal_moment,
            "pipeline_version": "B2-03",
        },
    )

    # ── TTS (optional, non-blocking) ──────────────────────────────────────
    audio_url: str | None = None
    if respond_with_audio and voice_id:
        audio_url = await _generate_tts(response_text, character_slug, voice_id)

    return {
        "response": response_text,
        "character_slug": character_slug,
        "model": model,
        "mood": effective_mood,
        "energy": effective_energy,
        "tone": tone_directive,
        "is_reveal_moment": is_reveal_moment,
        "audio_url": audio_url,
        "voice_id": voice_id,
    }


# ── Phase functions (each independently testable) ────────────────────────

async def phase_1_load_state(character_slug: str) -> dict[str, Any]:
    """Phase 1: Load current character state (mood, energy, arc_position)."""
    try:
        state = await get_character_state(character_slug)
        logger.info(
            "Phase 1 [%s]: mood=%s energy=%.2f",
            character_slug,
            state.get("mood", "neutral"),
            float(state.get("energy", 0.75)),
        )
        return state
    except Exception as e:
        logger.warning("Phase 1 [%s] failed, using defaults: %s", character_slug, e)
        return {"mood": "neutral", "energy": 0.75}


async def phase_2_apply_context(
    character_slug: str,
    user_message: str,
    channel: str,
) -> dict[str, Any]:
    """Phase 2: Run orchestrator to get enriched context with mood/event processing."""
    try:
        from runtime.characters.orchestrator import process_character_turn

        result = await process_character_turn(character_slug, user_message, channel)
        logger.info(
            "Phase 2 [%s]: orchestrator returned context with mood=%s energy_band=%s",
            character_slug,
            result.get("context", {}).get("mood", "?"),
            result.get("context", {}).get("energy_band", "?"),
        )
        return result
    except Exception as e:
        logger.warning(
            "Phase 2 [%s] orchestrator failed, using empty additions: %s",
            character_slug, e,
        )
        return {
            "context": {"mood": "neutral", "energy": 0.75, "energy_band": "moderate"},
            "event_result": None,
            "system_prompt_additions": "",
        }


def phase_3_select_tone(
    mood: str,
    energy_band: str,
    character_slug: str | None = None,
) -> str:
    """Phase 3: Select tone directive based on mood and energy band.

    If *character_slug* is provided and the character has custom tone
    directives, those are used.  Otherwise falls back to the generic
    TONE_DIRECTIVES table.
    """
    _load_character_tone_overrides()

    # Try character-specific tones first
    if character_slug and character_slug in _CHARACTER_TONE_OVERRIDES:
        char_tones = _CHARACTER_TONE_OVERRIDES[character_slug]
        mood_tones = char_tones.get(mood, char_tones.get("neutral", {}))
        directive = mood_tones.get(energy_band)
        if directive:
            logger.info(
                "Phase 3: mood=%s energy_band=%s slug=%s -> character tone selected",
                mood, energy_band, character_slug,
            )
            return directive

    # Generic fallback
    mood_tones = TONE_DIRECTIVES.get(mood, TONE_DIRECTIVES.get("neutral", {}))
    directive = mood_tones.get(energy_band, _DEFAULT_TONE)
    logger.info("Phase 3: mood=%s energy_band=%s -> generic tone selected", mood, energy_band)
    return directive


async def phase_4_generate_response(
    prompt: str,
    system_prompt: str,
    model: str,
    character_slug: str,
) -> str:
    """Phase 4: Call Claude with the enriched system prompt."""
    try:
        response_text = await call_claude(
            prompt=prompt,
            system=system_prompt,
            model=model,
            max_tokens=1024,
            client_id=settings.sparkle_internal_client_id,
            agent_id=f"character-{character_slug}",
            purpose="character_pipeline",
        )
        logger.info("Phase 4 [%s]: response generated (%d chars)", character_slug, len(response_text))
        return response_text
    except Exception as exc:
        logger.error("Phase 4 [%s] LLM call failed: %s", character_slug, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Character response generation failed for '{character_slug}': {exc}",
        ) from exc


async def phase_5_update_state(
    character_slug: str,
    user_message: str,
    response_text: str,
) -> None:
    """Phase 5: Record conversation event and update mood/energy based on interaction."""
    try:
        # Record that a conversation exchange happened.
        # The orchestrator already evaluated events in phase 2 and updated state,
        # so here we just mark the exchange itself as a lightweight event.
        await record_character_event(
            slug=character_slug,
            event="conversation_exchange",
            mood_effect=None,       # don't override — orchestrator already set mood
            energy_delta=-0.02,     # slight energy cost per exchange
        )
        logger.info("Phase 5 [%s]: state updated (conversation_exchange)", character_slug)
    except Exception as e:
        # State update is best-effort — never block the response
        logger.warning("Phase 5 [%s] state update failed: %s", character_slug, e)


async def phase_6_persist(
    character_id: str,
    user_identifier: str,
    channel: str,
    user_message: str,
    character_response: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Phase 6: Persist conversation pair to character_conversations table."""
    try:
        now = datetime.now(timezone.utc)
        base_meta = metadata or {}

        await asyncio.to_thread(
            lambda: supabase.table("character_conversations").insert([
                {
                    "character_id": character_id,
                    "user_identifier": user_identifier,
                    "channel": channel,
                    "role": "user",
                    "content": user_message,
                    "metadata": {**base_meta, "role_type": "user"},
                    "created_at": now.isoformat(),
                },
                {
                    "character_id": character_id,
                    "user_identifier": user_identifier,
                    "channel": channel,
                    "role": "character",
                    "content": character_response,
                    "metadata": base_meta,
                    "created_at": (now + timedelta(seconds=1)).isoformat(),
                },
            ]).execute()
        )
        logger.info("Phase 6: conversation persisted for character_id=%s", character_id)
    except Exception as e:
        # Persistence failure is non-fatal — response was already generated
        logger.warning("Phase 6: conversation persistence failed: %s", e)


# ── Internal helpers ─────────────────────────────────────────────────────

async def _load_character_record(character_slug: str) -> dict[str, Any]:
    """Load character from Supabase characters table."""
    try:
        char_result = await asyncio.to_thread(
            lambda: supabase.table("characters")
            .select("*")
            .eq("slug", character_slug)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch character: {exc}",
        ) from exc

    character: dict[str, Any] | None = char_result.data if char_result else None
    if not character:
        raise HTTPException(
            status_code=404,
            detail=f"Character '{character_slug}' not found or inactive.",
        )
    return character


def _build_enriched_system_prompt(
    soul_prompt: str,
    lore_context: str,
    system_prompt_additions: str,
    tone_directive: str,
) -> str:
    """
    Assemble the full system prompt from all components.

    Order:
      1. Soul prompt (core personality)
      2. Lore context (public lore)
      3. Orchestrator additions (mood, energy, reaction hints)
      4. Tone directive (how to speak)
    """
    parts: list[str] = []

    if soul_prompt:
        parts.append(soul_prompt)

    if lore_context:
        parts.append(f"--- Contexto sobre sua história ---\n{lore_context}")

    if system_prompt_additions:
        parts.append(f"--- Estado atual ---\n{system_prompt_additions}")

    if tone_directive:
        parts.append(f"--- Diretiva de tom ---\n{tone_directive}")

    return "\n\n".join(parts)


async def _get_character_history(
    character_id: str,
    user_identifier: str,
    channel: str,
    limit: int = 8,
) -> list[dict]:
    """Fetch conversation history in chronological order."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("character_conversations")
            .select("role, content")
            .eq("character_id", character_id)
            .eq("user_identifier", user_identifier)
            .eq("channel", channel)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = res.data or []
        return list(reversed(items))  # chronological: oldest first
    except Exception as e:
        logger.warning("Failed to fetch history: %s", e)
        return []


def _format_history(history: list[dict], character_name: str) -> str:
    """Format history as text for prompt injection."""
    if not history:
        return ""
    lines: list[str] = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        label = "Usuário" if role == "user" else character_name
        lines.append(f"{label}: {content}")
    return "\n".join(lines) + "\n"


async def _generate_tts(
    text: str,
    character_slug: str,
    voice_id: str,
) -> str | None:
    """Generate TTS audio URL. Non-fatal on failure."""
    try:
        from runtime.utils.tts import text_to_audio_url

        audio_url = await asyncio.to_thread(
            text_to_audio_url,
            text,
            f"character_{character_slug}",
            voice_id,
            "character-audio",
        )
        return audio_url
    except Exception as e:
        logger.warning("TTS failed for %s: %s", character_slug, e)
        return None
