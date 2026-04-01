"""
Character router — S5-01.

POST /character/message  — envia mensagem para um personagem (com TTS opcional)
GET  /character/{slug}   — retorna perfil público do personagem (sem soul_prompt / lore secreto)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.characters.handler import send_character_message

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
