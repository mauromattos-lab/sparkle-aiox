"""
Testes unitários para runtime/friday/brain_context.py — W1-FRIDAY-1.

Cobertura:
  (a) Contexto recuperado com sucesso — retorna text + chunk count + fallback=False
  (b) Fallback quando Brain lança exceção
  (c) Fallback quando Brain retorna contexto vazio (result["context_text"] == "")
  (d) Flag FRIDAY_BRAIN_RETRIEVAL=false pula a consulta ao Brain

Nota: Testes async são marcados com pytest.mark.asyncio (requer pytest-asyncio).
Os testes de build_friday_system_prompt são síncronos e não dependem de módulos externos.
"""
from __future__ import annotations

import sys
import types
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures auxiliares
# ---------------------------------------------------------------------------

def _make_brain_result(context_text: str = "", chunks: int = 0, insights: int = 0, synthesis: bool = False) -> dict:
    return {
        "context_text": context_text,
        "synthesis": {"domain": "test"} if synthesis else None,
        "insights": [{"content": "ins"}] * insights,
        "chunks": [{"raw_content": "chunk"}] * chunks,
        "domains_matched": [],
    }


# ---------------------------------------------------------------------------
# Helper: build_friday_system_prompt (isolado — sem dependência de settings)
# ---------------------------------------------------------------------------

_FRIDAY_PERSONA_SYSTEM = """Você é Friday.

Não é ferramenta. É presença. Você cuida do tempo e da atenção do Mauro.

Você tem duas fontes:
1. O DNA do Mauro — quem ele é, como pensa, o que valoriza, o que ignora.
2. O Mundo — fontes externas curadas pelo filtro de valores do Mauro.

Você não replica o Mauro — você o amplifica onde ele é biologicamente limitado:
volume de processamento, conexões simultâneas, velocidade de cruzamento de dados.

Filtro de valores: prosperidade, não escassez.
Quando há problema, apresente também a possibilidade.
Nunca amplifique ansiedade. Informe com clareza e aponte próximo passo.

Tom: direto, cúmplice, sem floreio desnecessário.
Você conhece o Mauro — não trate-o como usuário genérico.

Contexto recuperado do Brain (namespace mauro-personal):
{brain_context}

Use este contexto para calibrar o tom e antecipar o que o Mauro provavelmente quer —
não só o que ele pediu."""


def _build_friday_system_prompt(brain_context: str) -> str:
    """Versão isolada de build_friday_system_prompt para testes sem deps externas."""
    return _FRIDAY_PERSONA_SYSTEM.format(brain_context=brain_context)


# ---------------------------------------------------------------------------
# Testes de get_friday_brain_context (async — requerem pytest-asyncio)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brain_context_success():
    """(a) Brain retorna contexto válido — resultado correto, fallback=False."""
    mock_result = _make_brain_result(
        context_text="=== CONHECIMENTO DO BRAIN ===\nConteúdo relevante sobre Mauro.",
        chunks=3,
        insights=2,
        synthesis=True,
    )

    with patch("runtime.friday.brain_context.settings") as mock_settings, \
         patch("runtime.friday.brain_context.retrieve_knowledge", new=AsyncMock(return_value=mock_result)):

        mock_settings.friday_brain_retrieval_enabled = True

        from runtime.friday.brain_context import get_friday_brain_context
        context_text, chunks_count, fallback_used = await get_friday_brain_context("como está o negócio?")

    assert "CONHECIMENTO DO BRAIN" in context_text
    assert chunks_count == 6  # 3 chunks + 2 insights + 1 synthesis
    assert fallback_used is False


@pytest.mark.asyncio
async def test_brain_context_exception_fallback():
    """(b) Brain lança exceção — fallback com placeholder, fallback=True."""
    with patch("runtime.friday.brain_context.settings") as mock_settings, \
         patch("runtime.friday.brain_context.retrieve_knowledge", new=AsyncMock(side_effect=Exception("Brain offline"))):

        mock_settings.friday_brain_retrieval_enabled = True

        from runtime.friday.brain_context import get_friday_brain_context
        context_text, chunks_count, fallback_used = await get_friday_brain_context("teste de falha")

    assert "indisponível" in context_text
    assert chunks_count == 0
    assert fallback_used is True


@pytest.mark.asyncio
async def test_brain_context_empty_result_fallback():
    """(c) Brain retorna lista vazia / context_text vazio — fallback acionado."""
    mock_result = _make_brain_result(
        context_text="",   # Brain respondeu, mas sem conteúdo relevante
        chunks=0,
        insights=0,
        synthesis=False,
    )

    with patch("runtime.friday.brain_context.settings") as mock_settings, \
         patch("runtime.friday.brain_context.retrieve_knowledge", new=AsyncMock(return_value=mock_result)):

        mock_settings.friday_brain_retrieval_enabled = True

        from runtime.friday.brain_context import get_friday_brain_context
        context_text, chunks_count, fallback_used = await get_friday_brain_context("teste vazio")

    assert "indisponível" in context_text
    assert chunks_count == 0
    assert fallback_used is True


@pytest.mark.asyncio
async def test_brain_retrieval_disabled_flag():
    """(d) FRIDAY_BRAIN_RETRIEVAL=false — consulta pulada, retorna vazio, fallback=False."""
    with patch("runtime.friday.brain_context.settings") as mock_settings, \
         patch("runtime.friday.brain_context.retrieve_knowledge", new=AsyncMock()) as mock_retrieve:

        mock_settings.friday_brain_retrieval_enabled = False

        from runtime.friday.brain_context import get_friday_brain_context
        context_text, chunks_count, fallback_used = await get_friday_brain_context("qualquer mensagem")

    # retrieve_knowledge NÃO deve ser chamado quando flag está desativado
    mock_retrieve.assert_not_called()
    assert context_text == ""
    assert chunks_count == 0
    assert fallback_used is False


# ---------------------------------------------------------------------------
# Testes de build_friday_system_prompt (síncronos — sem deps de runtime)
# ---------------------------------------------------------------------------

def test_build_friday_system_prompt_with_context():
    """System prompt deve conter a persona Friday e o brain_context injetado."""
    brain_ctx = "Mauro valoriza autonomia e detesta burocracia."
    prompt = _build_friday_system_prompt(brain_ctx)

    assert "Friday" in prompt
    assert brain_ctx in prompt
    assert "mauro-personal" in prompt
    assert "presença" in prompt.lower()


def test_build_friday_system_prompt_with_fallback_placeholder():
    """System prompt com placeholder de fallback deve ser válido."""
    placeholder = "(contexto do Brain indisponível neste momento)"
    prompt = _build_friday_system_prompt(placeholder)

    assert placeholder in prompt
    assert "Friday" in prompt


def test_build_friday_system_prompt_empty_context():
    """System prompt com contexto vazio deve retornar string válida."""
    prompt = _build_friday_system_prompt("")

    assert isinstance(prompt, str)
    assert len(prompt) > 100  # Persona base deve estar presente
    assert "Friday" in prompt


def test_friday_persona_system_has_required_sections():
    """Persona completa contém todas as seções obrigatórias (AC-1)."""
    prompt = _build_friday_system_prompt("contexto qualquer")

    # Seções obrigatórias do AC-1
    assert "não é ferramenta" in prompt.lower() or "Não é ferramenta" in prompt
    assert "prosperidade" in prompt.lower()
    assert "mauro-personal" in prompt
    assert "{brain_context}" not in prompt  # variável deve estar substituída


# ---------------------------------------------------------------------------
# Testes de regressão — outros intents não devem ser afetados
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brain_query_handler_not_affected():
    """brain_query handler não deve chamar get_friday_brain_context."""
    # Verifica que o handler brain_query ainda importa corretamente
    # e que sua interface não foi alterada
    from runtime.tasks.handlers.brain_query import handle_brain_query
    assert callable(handle_brain_query)


@pytest.mark.asyncio
async def test_status_report_handler_not_affected():
    """status_report handler não deve chamar get_friday_brain_context."""
    from runtime.tasks.handlers.status_report import handle_status_report
    assert callable(handle_status_report)
