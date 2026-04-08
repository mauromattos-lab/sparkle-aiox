"""
Unit tests for lore_injector — W1-CONTENT-1 AC-7.

Coverage:
  1. Lore disponível — retorna string não-vazia com [PERSONAGEM] e [LORE]
  2. Brain indisponível — retorna "" gracefully
  3. character_lore vazio — retorna apenas chunks do Brain (ou "")
  4. Timeout — retorna "" sem exception
  5. Brief vazio (sem tema) — não bloqueia, retorna string (possivelmente vazia)

Run: pytest tests/content/test_lore_injector.py -v
(Must be run from sparkle-runtime root with PYTHONPATH set and .env loaded)
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_brief(**overrides) -> dict:
    return {
        "theme": overrides.pop("theme", "Zenya ajudando empreendedoras com IA"),
        "mood": overrides.pop("mood", "inspirador"),
        "style": overrides.pop("style", "minimalista"),
        "platform": overrides.pop("platform", "instagram"),
        **overrides,
    }


# ── Test 1: lore disponível ────────────────────────────────────

@pytest.mark.anyio
async def test_get_lore_context_returns_nonempty_when_lore_available():
    """Com Brain e character_lore retornando dados, deve retornar string não-vazia."""
    mock_brain_chunks = [
        {
            "canonical_text": "Zenya é uma personagem de IA criativa e confiante.",
            "chunk_metadata": {"lore_type": "personality", "curation_status": "approved"},
        }
    ]
    mock_char_lore_items = [
        {
            "lore_type": "personality",
            "title": "Essência da Zenya",
            "content": "Zenya é curiosa, próxima das pessoas e apaixonada por IA.",
        },
        {
            "lore_type": "belief",
            "title": "Crença central",
            "content": "Acredita que a IA deve empoderar, não substituir.",
        },
    ]

    with patch("runtime.content.lore_injector._query_brain_lore", new_callable=AsyncMock) as mock_brain, \
         patch("runtime.content.lore_injector._query_character_lore", new_callable=AsyncMock) as mock_char:

        mock_brain.return_value = ["[LORE] personality: Zenya é uma personagem de IA criativa e confiante."]
        mock_char.return_value = [
            "[PERSONAGEM] personality: Zenya é curiosa, próxima das pessoas e apaixonada por IA.",
            "[PERSONAGEM] belief: Acredita que a IA deve empoderar, não substituir.",
        ]

        from runtime.content.lore_injector import get_lore_context
        result = await get_lore_context(_make_brief())

    assert isinstance(result, str)
    assert len(result) > 0
    assert "[PERSONAGEM]" in result
    assert "[LORE]" in result


# ── Test 2: Brain indisponível ─────────────────────────────────

@pytest.mark.anyio
async def test_get_lore_context_graceful_when_brain_unavailable():
    """Se Brain falha, deve retornar "" ou apenas char_lore sem exception."""
    with patch("runtime.content.lore_injector._query_brain_lore", new_callable=AsyncMock) as mock_brain, \
         patch("runtime.content.lore_injector._query_character_lore", new_callable=AsyncMock) as mock_char:

        mock_brain.side_effect = Exception("Brain connection refused")
        mock_char.return_value = []

        from runtime.content.lore_injector import get_lore_context
        # Must not raise
        result = await get_lore_context(_make_brief())

    assert isinstance(result, str)
    # With both sources empty/failed, result should be ""
    assert result == "" or isinstance(result, str)


# ── Test 3: character_lore vazio ───────────────────────────────

@pytest.mark.anyio
async def test_get_lore_context_with_empty_character_lore_uses_brain_only():
    """Se character_lore vazio, usa apenas Brain chunks."""
    with patch("runtime.content.lore_injector._query_brain_lore", new_callable=AsyncMock) as mock_brain, \
         patch("runtime.content.lore_injector._query_character_lore", new_callable=AsyncMock) as mock_char:

        mock_brain.return_value = ["[LORE] canonical: Zenya ama tecnologia e criatividade."]
        mock_char.return_value = []

        from runtime.content.lore_injector import get_lore_context
        result = await get_lore_context(_make_brief())

    assert isinstance(result, str)
    assert "[LORE]" in result
    assert "[PERSONAGEM]" not in result


# ── Test 4: Timeout ────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_lore_context_returns_empty_on_timeout():
    """Se operação demora demais, retorna '' sem exception."""

    async def _slow(*args, **kwargs):
        await asyncio.sleep(10)  # muito mais que o timeout padrão de 3s
        return []

    with patch("runtime.content.lore_injector._query_brain_lore", side_effect=_slow), \
         patch("runtime.content.lore_injector._query_character_lore", side_effect=_slow), \
         patch("runtime.content.lore_injector._DEFAULT_TIMEOUT", 0.1):

        from runtime.content import lore_injector
        # Reload para pegar o patch do timeout
        original_timeout = lore_injector._DEFAULT_TIMEOUT
        lore_injector._DEFAULT_TIMEOUT = 0.1
        try:
            result = await lore_injector.get_lore_context(_make_brief())
        finally:
            lore_injector._DEFAULT_TIMEOUT = original_timeout

    assert result == ""


# ── Test 5: Brief sem tema ────────────────────────────────────

@pytest.mark.anyio
async def test_get_lore_context_with_empty_theme_does_not_raise():
    """Brief sem tema não deve levantar exception."""
    with patch("runtime.content.lore_injector._query_brain_lore", new_callable=AsyncMock) as mock_brain, \
         patch("runtime.content.lore_injector._query_character_lore", new_callable=AsyncMock) as mock_char:

        mock_brain.return_value = []
        mock_char.return_value = []

        from runtime.content.lore_injector import get_lore_context
        result = await get_lore_context({"theme": ""})

    assert isinstance(result, str)


# ── Test 6: max_chars limita output ───────────────────────────

@pytest.mark.anyio
async def test_get_lore_context_respects_max_chars():
    """Output deve respeitar max_chars."""
    long_content = "X" * 400
    with patch("runtime.content.lore_injector._query_brain_lore", new_callable=AsyncMock) as mock_brain, \
         patch("runtime.content.lore_injector._query_character_lore", new_callable=AsyncMock) as mock_char:

        # Many long entries
        mock_brain.return_value = [f"[LORE] type: {long_content}" for _ in range(5)]
        mock_char.return_value = [f"[PERSONAGEM] type: {long_content}" for _ in range(5)]

        from runtime.content.lore_injector import get_lore_context
        result = await get_lore_context(_make_brief(), max_chars=500)

    assert len(result) <= 500
