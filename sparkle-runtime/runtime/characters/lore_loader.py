"""
Lore loader — busca lore público de um personagem para injetar no system prompt.

Filtra apenas `is_public=true` e respeita `reveal_after` (não exibe lore ainda não liberado).
Retorna string formatada pronta para concatenar ao soul_prompt.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase


async def load_public_lore(character_id: str, max_chars: int = 2000) -> str:
    """
    Busca lore público do personagem e retorna como bloco de texto.

    Args:
        character_id: UUID do personagem na tabela `characters`.
        max_chars: Limite de caracteres do bloco retornado (aprox. 500 tokens).

    Returns:
        String formatada com o lore disponível, ou "" se nenhum lore público existir.
    """
    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        result = await asyncio.to_thread(
            lambda: supabase.table("character_lore")
            .select("lore_type, title, content")
            .eq("character_id", character_id)
            .eq("is_public", True)
            .or_(f"reveal_after.is.null,reveal_after.lte.{now_iso}")
            .order("created_at", desc=False)
            .execute()
        )

        lore_items: list[dict] = result.data or []

        if not lore_items:
            return ""

        parts: list[str] = []
        total = 0
        for item in lore_items:
            title = item.get("title", "")
            content = item.get("content", "")
            fragment = f"[{item.get('lore_type', 'lore')}] {title}: {content}"
            if total + len(fragment) > max_chars:
                break
            parts.append(fragment)
            total += len(fragment)

        return "\n".join(parts)

    except Exception as e:
        print(f"[lore_loader] Falha ao carregar lore de {character_id}: {e}")
        return ""
