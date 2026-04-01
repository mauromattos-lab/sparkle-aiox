"""
Character handler — S5-01.

Orquestra a conversa com um personagem do universo Sparkle:
  1. Busca o personagem por slug na tabela `characters`
  2. Busca histórico de conversa (últimas 8 msgs) em `character_conversations`
  3. Carrega lore público via lore_loader
  4. Monta system_prompt enriquecido (soul_prompt + lore)
  5. Invoca o agente associado via invoke_agent (com system_prompt_override)
  6. Persiste a troca em `character_conversations`
  7. Gera TTS se solicitado e voice_id disponível
  8. Retorna {response, character_slug, model, audio_url}

Personagem é stateful por design: histórico persiste no Supabase.
Agente associado é stateless (character-runner genérico) — a alma vem do soul_prompt.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import HTTPException

from runtime.db import supabase
from runtime.agents.handler import invoke_agent
from runtime.characters.lore_loader import load_public_lore


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

    Args:
        character_slug: Identificador único do personagem (ex: "finch").
        message: Mensagem do usuário.
        from_number: Identificador do usuário (número WhatsApp, @username, etc.).
        context: Metadados extras (channel, client_id, etc.).
        channel: Canal de origem (whatsapp, instagram, portal, etc.).
        respond_with_audio: Se True e personagem tiver voice_id, gera TTS.

    Returns:
        dict com keys: response, character_slug, model, audio_url (nullable), voice_id (nullable).

    Raises:
        HTTPException 404 se personagem não encontrado ou inativo.
        HTTPException 503 se personagem não tiver agente vinculado.
        HTTPException 500 em caso de erro na invocação.
    """
    ctx = context or {}

    # ── 1. Buscar personagem por slug ──────────────────────────────────────
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
        raise HTTPException(status_code=500, detail=f"Falha ao buscar personagem: {exc}") from exc

    character: dict[str, Any] | None = char_result.data if char_result else None

    if not character:
        raise HTTPException(
            status_code=404,
            detail=f"Personagem '{character_slug}' não encontrado ou inativo.",
        )

    # ── 2. Verificar agente vinculado ──────────────────────────────────────
    primary_agent_id: str | None = character.get("primary_agent_id")
    if not primary_agent_id:
        raise HTTPException(
            status_code=503,
            detail=f"Personagem '{character_slug}' não tem agente ativo vinculado.",
        )

    character_id: str = character["id"]

    # ── 3. Buscar histórico (últimas 8 mensagens, cronológico) ─────────────
    history = await _get_character_history(character_id, from_number, channel, limit=8)

    # ── 4. Carregar lore público ───────────────────────────────────────────
    lore_context = await load_public_lore(character_id)

    # ── 5. Montar system_prompt enriquecido ────────────────────────────────
    soul_prompt: str = character.get("soul_prompt") or ""
    system_prompt = soul_prompt

    if lore_context:
        system_prompt += f"\n\n--- Contexto sobre sua história ---\n{lore_context}"

    # Injetar histórico como contexto de conversa no prompt
    history_text = _format_history(history, character.get("name", character_slug))
    if history_text:
        current_message = f"{history_text}Usuário: {message}\n{character.get('name', character_slug)}:"
    else:
        current_message = message

    # ── 6. Invocar agente com system_prompt_override ───────────────────────
    invoke_context = {
        **ctx,
        "system_prompt_override": system_prompt,
        "user_identifier": from_number,
        "channel": channel,
        "character_slug": character_slug,
    }

    try:
        result = await invoke_agent(
            agent_id=primary_agent_id,
            message=current_message,
            context=invoke_context,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha na invocação do personagem '{character_slug}': {exc}",
        ) from exc

    response_text: str = result["response"]
    model_used: str = result.get("model", "")

    # ── 7. Persistir conversa ──────────────────────────────────────────────
    await _save_conversation(
        character_id=character_id,
        user_identifier=from_number,
        channel=channel,
        user_message=message,
        character_response=response_text,
    )

    # ── 8. TTS opcional ───────────────────────────────────────────────────
    audio_url: str | None = None
    voice_id: str | None = character.get("voice_id")

    if respond_with_audio and voice_id:
        try:
            from runtime.utils.tts import text_to_audio_url
            audio_url = await asyncio.to_thread(
                text_to_audio_url,
                response_text,
                f"character_{character_slug}",
                voice_id,
                "character-audio",
            )
        except Exception as e:
            print(f"[character_handler] TTS falhou para {character_slug}: {e}")
            # TTS failure is non-fatal — resposta de texto ainda é retornada

    return {
        "response": response_text,
        "character_slug": character_slug,
        "model": model_used,
        "audio_url": audio_url,
        "voice_id": voice_id,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_character_history(
    character_id: str,
    user_identifier: str,
    channel: str,
    limit: int = 8,
) -> list[dict]:
    """Busca histórico de conversa em ordem cronológica."""
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
        return list(reversed(items))  # cronológico: mais antigo primeiro
    except Exception as e:
        print(f"[character_handler] Falha ao buscar histórico: {e}")
        return []


def _format_history(history: list[dict], character_name: str) -> str:
    """Formata histórico como texto para injetar no prompt."""
    if not history:
        return ""
    lines: list[str] = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        label = "Usuário" if role == "user" else character_name
        lines.append(f"{label}: {content}")
    return "\n".join(lines) + "\n"


async def _save_conversation(
    character_id: str,
    user_identifier: str,
    channel: str,
    user_message: str,
    character_response: str,
) -> None:
    """Persiste o par user/character no histórico de conversas."""
    try:
        now = datetime.now(timezone.utc)
        await asyncio.to_thread(
            lambda: supabase.table("character_conversations").insert([
                {
                    "character_id": character_id,
                    "user_identifier": user_identifier,
                    "channel": channel,
                    "role": "user",
                    "content": user_message,
                    "created_at": now.isoformat(),
                },
                {
                    "character_id": character_id,
                    "user_identifier": user_identifier,
                    "channel": channel,
                    "role": "character",
                    "content": character_response,
                    "created_at": (now + timedelta(seconds=1)).isoformat(),
                },
            ]).execute()
        )
    except Exception as e:
        print(f"[character_handler] Falha ao salvar conversa: {e}")
