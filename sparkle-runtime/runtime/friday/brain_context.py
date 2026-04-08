"""
Friday — Brain Context Loader (W1-FRIDAY-1).

Responsável por:
  1. Consultar o Brain no namespace `mauro-personal` antes de cada resposta de chat.
  2. Formatar o contexto recuperado como string pronta para injeção no system prompt.
  3. Tratar exceções com fallback gracioso — Friday nunca silencia por erro no Brain.
  4. Registrar cada consulta em `friday_context_log`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt da Friday com persona completa
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


def build_friday_system_prompt(brain_context: str) -> str:
    """
    Monta o system prompt completo da Friday com o contexto do Brain injetado.

    Args:
        brain_context: Texto formatado com chunks recuperados do Brain,
                       ou placeholder de fallback se indisponível.

    Returns:
        System prompt completo como string.
    """
    return _FRIDAY_PERSONA_SYSTEM.format(brain_context=brain_context)


# ---------------------------------------------------------------------------
# Brain context retriever
# ---------------------------------------------------------------------------

async def get_friday_brain_context(query: str) -> tuple[str, int, bool]:
    """
    Consulta o Brain no namespace `mauro-personal` usando a query do Mauro.

    Retorna uma tupla (brain_context, chunks_count, fallback_used):
      - brain_context: string formatada com o contexto recuperado (ou placeholder)
      - chunks_count: número de chunks recuperados
      - fallback_used: True se o fallback foi acionado

    Nunca lança exceção — sempre retorna resultado utilizável.
    """
    # Verificar flag de controle
    if not settings.friday_brain_retrieval_enabled:
        logger.info("[FRIDAY] FRIDAY_BRAIN_RETRIEVAL=false — pulando consulta ao Brain")
        return ("", 0, False)

    try:
        from runtime.brain.knowledge import retrieve_knowledge

        # Brain chunks do namespace mauro-personal são armazenados com brain_owner="mauro-personal".
        # retrieve_knowledge filtra por brain_owner para isolar chunks do Mauro.
        result = await retrieve_knowledge(
            topic=query,
            brain_owner="mauro-personal",
            max_insights=3,
            max_chunks=4,
            include_synthesis=True,
        )

        context_text: str = result.get("context_text", "")
        chunks: list = result.get("chunks", [])
        insights: list = result.get("insights", [])

        # Conta chunks + insights como "unidades de contexto recuperadas"
        total_retrieved = len(chunks) + len(insights)
        if result.get("synthesis"):
            total_retrieved += 1  # síntese conta como 1 unidade

        if not context_text.strip():
            # Brain respondeu mas sem conteúdo relevante
            logger.warning(
                "[FRIDAY] Brain indisponível para contexto — respondendo sem contexto mauro-personal"
            )
            return (
                "(contexto do Brain indisponível neste momento)",
                0,
                True,
            )

        logger.info(
            "[FRIDAY] Brain consultado: %d chunks recuperados do namespace mauro-personal",
            total_retrieved,
        )
        return (context_text, total_retrieved, False)

    except Exception as exc:
        logger.warning(
            "[FRIDAY] Brain indisponível para contexto — respondendo sem contexto mauro-personal. Erro: %s",
            exc,
        )
        return (
            "(contexto do Brain indisponível neste momento)",
            0,
            True,
        )


# ---------------------------------------------------------------------------
# Context log recorder
# ---------------------------------------------------------------------------

async def log_friday_context(
    interaction_id: Optional[str],
    chunks_retrieved: int,
    used_in_response: bool = True,
    fallback_used: bool = False,
) -> None:
    """
    Registra a consulta ao Brain em `friday_context_log`.
    Falha silenciosamente — não deve interferir na resposta principal.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(
            lambda: supabase.table("friday_context_log").insert({
                "interaction_id": interaction_id,
                "brain_namespace": "mauro-personal",
                "chunks_retrieved": chunks_retrieved,
                "used_in_response": used_in_response,
                "fallback_used": fallback_used,
                "created_at": now,
            }).execute()
        )
    except Exception as exc:
        logger.warning("[FRIDAY] Falha ao registrar friday_context_log: %s", exc)
