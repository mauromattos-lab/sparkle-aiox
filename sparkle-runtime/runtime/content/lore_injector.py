"""
Lore Injector — W1-CONTENT-1.

Recupera lore canônico da Zenya de duas fontes e formata um bloco de contexto
para injeção no prompt do copy_specialist antes da geração de conteúdo.

Fontes:
  1. Brain namespace 'sparkle-lore' — top-3 chunks relevantes ao tema (similaridade semântica)
  2. character_lore table — entries de personality, arc, belief para Zenya

Interface pública:
  async def get_lore_context(brief: dict, max_chars: int = 1500) -> str

Nunca bloqueia — retorna "" em caso de falha em qualquer fonte.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase

# Timeout total para todo o processo de injeção
_DEFAULT_TIMEOUT = float(os.environ.get("LORE_INJECTOR_TIMEOUT_SECONDS", "3"))

# Zenya character slug (mais robusto que UUID — funciona em qualquer ambiente)
_ZENYA_SLUG = "zenya"

# lore_types a incluir do character_lore
_INJECT_LORE_TYPES = ("personality", "arc", "belief")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Brain query ────────────────────────────────────────────────

async def _query_brain_lore(theme: str, top_k: int = 3) -> list[str]:
    """
    Query Brain namespace 'sparkle-lore' por similaridade com o tema.

    Filtra curation_status='approved' via match_lore_chunks RPC.
    Retorna lista de strings formatadas como:
      [LORE] {lore_type}: {canonical_text[:200]}

    Retorna [] em qualquer erro — nunca bloqueia.
    """
    try:
        from runtime.brain.knowledge import _get_embedding

        embedding = await _get_embedding(theme)
        if not embedding:
            print("[lore_injector] embedding unavailable — Brain lore skipped")
            return []

        result = await asyncio.to_thread(
            lambda: supabase.rpc(
                "match_lore_chunks",
                {
                    "query_embedding": embedding,
                    "namespace_in": "sparkle-lore",
                    "match_count": top_k,
                },
            ).execute()
        )

        chunks = result.data or []
        parts: list[str] = []
        for chunk in chunks:
            # Excluir chunks com curation_status != 'approved'
            meta = chunk.get("chunk_metadata") or {}
            curation_status = meta.get("curation_status") or chunk.get("curation_status")
            # match_lore_chunks já filtra approved, mas checamos como garantia
            if curation_status and curation_status != "approved":
                continue

            canonical_text = (chunk.get("canonical_text") or "")[:200]
            lore_type = meta.get("lore_type") or "lore"
            if canonical_text:
                parts.append(f"[LORE] {lore_type}: {canonical_text}")

        return parts

    except Exception as exc:
        print(f"[lore_injector] Brain query error (non-blocking): {exc}")
        return []


# ── character_lore query ────────────────────────────────────────

async def _query_character_lore() -> list[str]:
    """
    Consulta character_lore WHERE character_slug='zenya'
    AND lore_type IN ('personality', 'arc', 'belief')
    AND is_public=true
    AND (reveal_after IS NULL OR reveal_after <= NOW()).

    Retorna lista de strings formatadas como:
      [PERSONAGEM] {lore_type}: {content[:300]}

    Retorna [] em qualquer erro — nunca bloqueia.
    """
    try:
        now_iso = _now_iso()

        result = await asyncio.to_thread(
            lambda: supabase.table("character_lore")
            .select("lore_type, title, content")
            .eq("character_slug", _ZENYA_SLUG)
            .eq("is_public", True)
            .in_("lore_type", list(_INJECT_LORE_TYPES))
            .or_(f"reveal_after.is.null,reveal_after.lte.{now_iso}")
            .order("created_at", desc=False)
            .execute()
        )

        items = result.data or []
        if not items:
            print("[lore_injector] character_lore returned 0 entries for zenya")
            return []

        parts: list[str] = []
        for item in items:
            lore_type = item.get("lore_type", "lore")
            content = (item.get("content") or "")[:300]
            if content:
                parts.append(f"[PERSONAGEM] {lore_type}: {content}")

        return parts

    except Exception as exc:
        print(f"[lore_injector] character_lore query error (non-blocking): {exc}")
        return []


# ── Main interface ─────────────────────────────────────────────

async def _build_lore_context(brief: dict, max_chars: int) -> str:
    """Inner implementation — pode ser envolvida em timeout externo."""
    theme = brief.get("theme", "")

    # Rodar Brain + character_lore em paralelo
    brain_task = asyncio.create_task(_query_brain_lore(theme, top_k=3))
    char_task = asyncio.create_task(_query_character_lore())
    brain_parts, char_parts = await asyncio.gather(brain_task, char_task)

    # character_lore tem maior peso estrutural — vem primeiro
    all_parts = char_parts + brain_parts

    if not all_parts:
        return ""

    # Montar bloco respeitando max_chars
    lines: list[str] = []
    total = 0
    for part in all_parts:
        if total + len(part) + 1 > max_chars:
            break
        lines.append(part)
        total += len(part) + 1  # +1 para \n

    return "\n".join(lines)


async def get_lore_context(brief: dict, max_chars: int = 1500) -> str:
    """
    Dado um content_brief, retorna bloco de contexto de lore da Zenya.

    Combina:
      - top-3 chunks relevantes do Brain (namespace='sparkle-lore')
      - entries de character_lore (personality, arc, belief) da Zenya

    Retorna string formatada pronta para inserir no prompt do copy_specialist.
    Retorna "" se lore indisponível — nunca bloqueia.

    Args:
        brief: content_brief dict com campo 'theme' (mínimo)
        max_chars: limite de caracteres do bloco de lore (default 1500 ≈ 375 tokens)

    Returns:
        String com lore formatado, ou "" se indisponível.
    """
    try:
        timeout = _DEFAULT_TIMEOUT
        return await asyncio.wait_for(
            _build_lore_context(brief, max_chars),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        print(f"[lore_injector] timeout after {_DEFAULT_TIMEOUT}s — returning empty lore")
        return ""
    except Exception as exc:
        print(f"[lore_injector] unexpected error (non-blocking): {exc}")
        return ""
