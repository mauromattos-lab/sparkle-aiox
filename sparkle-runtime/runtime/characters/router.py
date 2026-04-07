"""
Character router — S5-01 + B1-02 (Character State) + B2-02 (Orchestrator) + B2-03 (Pipeline).

POST /character/message                    — envia mensagem para um personagem (6-phase pipeline)
GET  /character/{slug}                     — retorna perfil público do personagem
GET  /character/{slug}/state               — retorna estado canônico (mood, energy, arc, etc.)
PATCH /character/{slug}/state              — atualiza campos do estado
POST /character/{slug}/event               — registra evento com efeitos em mood/energy
POST /character/{slug}/orchestrate/event   — avalia evento via Character Orchestrator (B2-02)
GET  /character/{slug}/orchestrate/context — contexto enriquecido para geração de resposta
POST /character/{slug}/orchestrate/turn    — processamento completo de turno (B2-02)
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.characters.handler import send_character_message
from runtime.characters.state import (
    get_character_state,
    update_character_state,
    record_character_event,
)
from runtime.characters.orchestrator import (
    evaluate_event,
    get_character_context,
    process_character_turn,
)

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────

class CharacterMessageRequest(BaseModel):
    slug: str                           # ex: "finch"
    message: str
    user_identifier: str                # ex: "5511999999999"
    channel: str = "whatsapp"
    respond_with_audio: bool = False    # True → gera TTS com a voz do personagem


class CharacterMessageResponse(BaseModel):
    response: str
    character_slug: str
    model: str
    mood: Optional[str] = None
    energy: Optional[float] = None
    tone: Optional[str] = None
    is_reveal_moment: bool = False
    audio_url: Optional[str] = None
    voice_id: Optional[str] = None


class CharacterProfileResponse(BaseModel):
    slug: str
    name: str
    tagline: Optional[str] = None
    specialty: str
    avatar_url: Optional[str] = None
    avatar_style: Optional[str] = None
    active_channels: list
    lore_status: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/message", response_model=CharacterMessageResponse)
async def character_message(req: CharacterMessageRequest):
    """
    Envia uma mensagem para um personagem e recebe a resposta em texto (e áudio opcional).

    - Busca personagem ativo por slug
    - Enriquece com lore público e histórico da conversa
    - Invoca agente associado com soul_prompt do personagem
    - Persiste a conversa em `character_conversations`
    - Se `respond_with_audio=True` e personagem tiver `voice_id`, gera TTS via ElevenLabs
    """
    result = await send_character_message(
        character_slug=req.slug,
        message=req.message,
        from_number=req.user_identifier,
        channel=req.channel,
        respond_with_audio=req.respond_with_audio,
    )
    return CharacterMessageResponse(**result)


@router.get("/{slug}", response_model=CharacterProfileResponse)
async def get_character_profile(slug: str):
    """
    Retorna o perfil público de um personagem.

    Nunca expõe: soul_prompt, personality_traits internos, lore secreto,
    universe_connections privadas ou primary_agent_id.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("characters")
            .select(
                "slug, name, tagline, specialty, "
                "avatar_url, avatar_style, active_channels, lore_status"
            )
            .eq("slug", slug)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao buscar personagem: {exc}") from exc

    character = result.data if result else None

    if not character:
        raise HTTPException(
            status_code=404,
            detail=f"Personagem '{slug}' não encontrado ou inativo.",
        )

    return CharacterProfileResponse(
        slug=character["slug"],
        name=character["name"],
        tagline=character.get("tagline"),
        specialty=character["specialty"],
        avatar_url=character.get("avatar_url"),
        avatar_style=character.get("avatar_style"),
        active_channels=character.get("active_channels") or [],
        lore_status=character["lore_status"],
    )


# ── Character State models ────────────────────────────────────────────────

class CharacterStateUpdate(BaseModel):
    mood: Optional[str] = None
    energy: Optional[float] = None
    arc_position: Optional[dict] = None
    personality_traits: Optional[dict] = None
    session_context: Optional[dict] = None


class CharacterEventRequest(BaseModel):
    event: str
    mood_effect: Optional[str] = None
    energy_delta: float = 0.0


class OrchestratorEventRequest(BaseModel):
    event_type: str
    event_data: Optional[dict] = None


class OrchestratorTurnRequest(BaseModel):
    user_message: str
    channel: str = "whatsapp"


# ── Character State endpoints (B1-02) ────────────────────────────────────

@router.get("/{slug}/state")
async def get_state(slug: str):
    """
    Returns the canonical state of a character (mood, energy, arc, traits, etc.).
    Auto-creates a default state row if none exists.
    """
    try:
        state = await get_character_state(slug)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao buscar estado do personagem '{slug}': {exc}",
        ) from exc
    return state


@router.patch("/{slug}/state")
async def patch_state(slug: str, body: CharacterStateUpdate):
    """
    Partial update of character state fields.
    Only provided (non-null) fields are updated.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return await get_character_state(slug)

    try:
        state = await update_character_state(slug, updates)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao atualizar estado do personagem '{slug}': {exc}",
        ) from exc
    return state


@router.post("/{slug}/event")
async def post_event(slug: str, body: CharacterEventRequest):
    """
    Record an event for a character, optionally changing mood and energy.

    - event: what happened (free text)
    - mood_effect: new mood string (optional)
    - energy_delta: value to add/subtract from energy, clamped to [0.00, 0.99]
    """
    try:
        state = await record_character_event(
            slug=slug,
            event=body.event,
            mood_effect=body.mood_effect,
            energy_delta=body.energy_delta,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao registrar evento para '{slug}': {exc}",
        ) from exc
    return state


# ── Character Orchestrator endpoints (B2-02) ────────────────────────────

@router.post("/{slug}/orchestrate/event")
async def orchestrate_event(slug: str, body: OrchestratorEventRequest):
    """
    Evaluate an event through the Character Orchestrator.

    The orchestrator determines mood shift, energy delta, reaction style,
    and whether this is a 'reveal moment' — all without LLM calls.

    Supported event_types: conversation_start, conversation_end,
    positive_feedback, negative_feedback, milestone, time_passage, lore_trigger.
    """
    try:
        result = await evaluate_event(
            character_slug=slug,
            event_type=body.event_type,
            event_data=body.event_data,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator evaluate_event failed for '{slug}': {exc}",
        ) from exc
    return result


@router.get("/{slug}/orchestrate/context")
async def orchestrate_context(slug: str):
    """
    Get the enriched character context built by the orchestrator.

    Includes: mood, energy, energy band, arc position, recent events,
    time-of-day style, and response generation hints.
    """
    try:
        context = await get_character_context(slug)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator get_character_context failed for '{slug}': {exc}",
        ) from exc
    return context


@router.post("/{slug}/orchestrate/turn")
async def orchestrate_turn(slug: str, body: OrchestratorTurnRequest):
    """
    Full turn processing through the Character Orchestrator.

    Loads state, evaluates events (conversation_start if new, sentiment
    detection from message), builds enriched context, and returns
    system_prompt_additions for the response generator.

    Does NOT call the LLM — returns context for the handler to use.
    """
    try:
        result = await process_character_turn(
            character_slug=slug,
            user_message=body.user_message,
            channel=body.channel,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator process_character_turn failed for '{slug}': {exc}",
        ) from exc
    return result
