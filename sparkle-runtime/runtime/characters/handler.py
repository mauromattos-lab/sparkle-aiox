"""
Character handler — S5-01 + B2-03.

Public entry point for character conversations.  Delegates to the 6-phase
response pipeline (B2-03) which integrates the Character Orchestrator for
mood-aware, tone-enriched responses.

The pipeline handles:
  1. Load character state (mood, energy, arc)
  2. Apply orchestrator context (events, time-of-day, sentiment)
  3. Select tone based on mood + energy
  4. Generate LLM response with enriched system prompt
  5. Update character state
  6. Persist conversation with metadata

Backward-compatible: callers still use send_character_message() as before.
"""
from __future__ import annotations

import logging
from typing import Any

from runtime.characters.pipeline import character_response_pipeline

logger = logging.getLogger(__name__)


async def send_character_message(
    character_slug: str,
    message: str,
    from_number: str,
    context: dict[str, Any] | None = None,
    channel: str = "whatsapp",
    respond_with_audio: bool = False,
) -> dict[str, Any]:
    """
    Processa uma mensagem para um personagem e retorna a resposta.

    Delegates entirely to the 6-phase character_response_pipeline (B2-03).

    Args:
        character_slug: Identificador único do personagem (ex: "finch").
        message: Mensagem do usuário.
        from_number: Identificador do usuário (número WhatsApp, @username, etc.).
        context: Metadados extras (channel, client_id, etc.). Reserved for future use.
        channel: Canal de origem (whatsapp, instagram, portal, etc.).
        respond_with_audio: Se True e personagem tiver voice_id, gera TTS.

    Returns:
        dict com keys: response, character_slug, model, mood, energy, tone,
        is_reveal_moment, audio_url (nullable), voice_id (nullable).

    Raises:
        HTTPException 404 se personagem não encontrado ou inativo.
        HTTPException 500 em caso de erro na geração.
    """
    logger.info(
        "send_character_message: slug=%s channel=%s from=%s",
        character_slug, channel, from_number,
    )

    result = await character_response_pipeline(
        character_slug=character_slug,
        user_message=message,
        from_number=from_number,
        channel=channel,
        respond_with_audio=respond_with_audio,
    )

    return result
