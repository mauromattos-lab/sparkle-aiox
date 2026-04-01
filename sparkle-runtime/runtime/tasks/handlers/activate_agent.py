"""
activate_agent handler — registra solicitação de ativação de agente AIOS.

Quando Mauro diz "ativa o @dev pra fazer X" ou "chama o @architect pra Y":
  1. Extrai o agente e a tarefa do payload
  2. Cria nova task no Supabase com task_type="agent_request"
  3. Retorna confirmação ao Mauro

Por ora não executa o agente de verdade — apenas registra e confirma.
A execução real será implementada no lifecycle management (Sprint futuro).
"""
from __future__ import annotations

from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase


# Agentes reconhecidos — para validação básica
_KNOWN_AGENTS = {
    "@dev", "@qa", "@architect", "@analyst",
    "@pm", "@po", "@sm", "@squad-creator", "@devops",
}


async def handle_activate_agent(task: dict) -> dict:
    """
    Registra solicitação de ativação de agente no Supabase.
    Retorna {"message": "<confirmação>"}.
    """
    payload = task.get("payload", {})

    agent = _extract_agent(payload)
    request = _extract_request(payload)

    if not agent:
        return {
            "message": (
                "Não identifiquei qual agente você quer acionar. "
                "Exemplo: 'ativa o @dev pra refatorar o router.py'"
            )
        }

    # Cria a task agent_request no Supabase
    agent_task_id = _create_agent_request(agent, request, task)

    agent_display = agent if agent.startswith("@") else f"@{agent}"

    if request:
        msg = (
            f"Acionei o {agent_display} com a tarefa: {request}. "
            f"ID da solicitação: {agent_task_id}. "
            f"Acompanhe pelo Supabase."
        )
    else:
        msg = (
            f"Acionei o {agent_display}. "
            f"ID da solicitação: {agent_task_id}. "
            f"Acompanhe pelo Supabase."
        )

    return {
        "message": msg,
        "agent": agent_display,
        "request": request,
        "agent_task_id": agent_task_id,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_agent(payload: dict) -> str:
    """
    Tenta extrair o agente do payload.
    Aceita: payload["agent"] direto, ou busca no original_text.
    """
    # Direto do dispatcher (já extraído)
    if payload.get("agent"):
        return payload["agent"].strip()

    # Tenta extrair do texto original via heurística simples
    text = payload.get("original_text", "").lower()
    for agent in _KNOWN_AGENTS:
        if agent in text:
            return agent

    return ""


def _extract_request(payload: dict) -> str:
    """
    Extrai a descrição da tarefa do payload.
    Aceita: payload["request"] direto, ou extrai do original_text.
    """
    if payload.get("request"):
        return payload["request"].strip()

    # Remove o nome do agente do texto para obter a tarefa
    text = payload.get("original_text", "")
    if not text:
        return ""

    # Limpa palavras de acionamento comuns
    import re
    clean = re.sub(
        r"\b(ativa|ative|chama|chame|aciona|acione|o|a|pra|para|fazer|faz)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Remove menções ao agente
    for agent in _KNOWN_AGENTS:
        clean = re.sub(re.escape(agent), "", clean, flags=re.IGNORECASE)

    return " ".join(clean.split()).strip()


def _create_agent_request(agent: str, request: str, parent_task: dict) -> str:
    """
    Insere task com task_type='agent_request' no Supabase.
    Usa agent_id='orion' (o orquestrador) pois os agentes AIOS (@dev, @architect, etc.)
    são personas do Claude Code — não existem como rows na tabela agents.
    O agente-alvo fica registrado no payload.
    Retorna o ID da task criada.
    """
    try:
        res = supabase.table("runtime_tasks").insert({
            "agent_id": "orion",   # orion é o orchestrator na DB; ele roteia para AIOS agents
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "agent_request",
            "payload": {
                "target_agent": agent,   # e.g. "@dev", "@architect"
                "request": request,
                "requested_by": "friday",
                "parent_task_id": parent_task.get("id"),
                "original_text": parent_task.get("payload", {}).get("original_text", ""),
            },
            "status": "pending",
            "priority": 5,
        }).execute()
        return res.data[0]["id"] if res.data else "unknown"
    except Exception as e:
        print(f"[activate_agent] failed to create agent_request task: {e}")
        return "error"
