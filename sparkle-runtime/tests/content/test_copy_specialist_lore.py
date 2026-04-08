"""
Tests for copy_specialist lore_context integration — W1-CONTENT-1 AC-7.

Coverage:
  1. Geração com lore_context — lore aparece no system prompt enviado ao LLM
  2. Geração sem lore_context — comportamento anterior não é alterado
  3. lore_context vazio ("") — mesmo comportamento de sem lore_context

Run: pytest tests/content/test_copy_specialist_lore.py -v
(Must be run from sparkle-runtime root with PYTHONPATH set and .env loaded)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


SAMPLE_LORE = (
    "[PERSONAGEM] personality: Zenya é curiosa, próxima das pessoas e apaixonada por IA.\n"
    "[LORE] canonical: Zenya ajuda empreendedoras a usar IA para crescer seus negócios."
)


# ── Test 1: lore_context entra no system prompt ────────────────

@pytest.mark.anyio
async def test_generate_copy_with_lore_context_uses_lore_in_prompt():
    """Quando lore_context fornecido, deve aparecer no system prompt do LLM."""
    captured_system = []

    async def _mock_call_claude(prompt, system=None, **kwargs):
        if system:
            captured_system.append(system)
        return '{"caption": "Caption de teste #zenya", "voice_script": "Script de teste."}'

    with patch("runtime.content.copy_specialist.call_claude", side_effect=_mock_call_claude):
        from runtime.content.copy_specialist import generate_copy
        result = await generate_copy(
            theme="Zenya e empreendedorismo feminino",
            mood="inspirador",
            style="minimalista",
            lore_context=SAMPLE_LORE,
        )

    assert len(captured_system) == 1
    system_used = captured_system[0]
    assert "LORE CANÔNICO DA ZENYA" in system_used
    assert SAMPLE_LORE in system_used
    assert "FIM DO LORE" in system_used
    assert result["caption"] is not None


# ── Test 2: sem lore_context — comportamento inalterado ────────

@pytest.mark.anyio
async def test_generate_copy_without_lore_context_uses_original_system_prompt():
    """Sem lore_context, system prompt deve ser exatamente COPY_SYSTEM_PROMPT."""
    from runtime.content.copy_specialist import COPY_SYSTEM_PROMPT
    captured_system = []

    async def _mock_call_claude(prompt, system=None, **kwargs):
        if system:
            captured_system.append(system)
        return '{"caption": "Caption sem lore #zenya", "voice_script": null}'

    with patch("runtime.content.copy_specialist.call_claude", side_effect=_mock_call_claude):
        from runtime.content.copy_specialist import generate_copy
        result = await generate_copy(
            theme="IA no cotidiano",
            mood="divertido",
            style="colorido",
        )

    assert len(captured_system) == 1
    assert captured_system[0] == COPY_SYSTEM_PROMPT
    assert "LORE CANÔNICO" not in captured_system[0]


# ── Test 3: lore_context="" — mesmo que sem lore ───────────────

@pytest.mark.anyio
async def test_generate_copy_with_empty_lore_context_uses_original_system_prompt():
    """lore_context='' deve se comportar como sem lore — sem modificar o prompt."""
    from runtime.content.copy_specialist import COPY_SYSTEM_PROMPT
    captured_system = []

    async def _mock_call_claude(prompt, system=None, **kwargs):
        if system:
            captured_system.append(system)
        return '{"caption": "Caption vazia lore #zenya", "voice_script": null}'

    with patch("runtime.content.copy_specialist.call_claude", side_effect=_mock_call_claude):
        from runtime.content.copy_specialist import generate_copy
        result = await generate_copy(
            theme="Autoconhecimento com IA",
            mood="reflexivo",
            style="clean",
            lore_context="",
        )

    assert len(captured_system) == 1
    assert captured_system[0] == COPY_SYSTEM_PROMPT


# ── Test 4: retorno correto com lore_context ──────────────────

@pytest.mark.anyio
async def test_generate_copy_returns_caption_and_voice_script_with_lore():
    """Resultado deve ter caption e voice_script mesmo com lore_context."""
    async def _mock_call_claude(prompt, system=None, **kwargs):
        return '{"caption": "Zenya transforma negócios 🚀 #zenya #ia #empreendedorismo", "voice_script": "A IA chegou pra ficar."}'

    with patch("runtime.content.copy_specialist.call_claude", side_effect=_mock_call_claude):
        from runtime.content.copy_specialist import generate_copy
        result = await generate_copy(
            theme="Zenya e o futuro dos negócios",
            mood="inspirador",
            style="minimalista",
            lore_context=SAMPLE_LORE,
        )

    assert "caption" in result
    assert "voice_script" in result
    assert len(result["caption"]) > 0
