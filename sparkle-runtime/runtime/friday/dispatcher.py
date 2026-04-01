"""
Friday — Intent dispatcher.
Takes a transcribed message and creates a runtime_task.
Uses Claude Haiku for intent classification (cheap + fast).
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

# Intent enum — add new intents here as Friday grows
INTENTS = [
    "status_report",         # "como estão os agentes?", "status", "agentes"
    "status_mrr",            # "qual o MRR?", "faturamento", "quanto tô faturando"
    "chat",                  # conversa livre, perguntas, dúvidas, qualquer coisa não estruturada
    "create_note",           # "anota X", "lembra que Y", "registra Z", "salva isso"
    "activate_agent",        # "ativa o @dev pra fazer X", "chama o arquiteto"
    "weekly_briefing",       # "resumo da semana", "o que rolou essa semana"
    "onboard_client",        # "onborda [nome] site:[url] tipo:[tipo]" — Sprint 8
    "brain_query",           # "brain, o que você sabe sobre X?", "consulta o brain sobre Y"
    "brain_ingest",          # "brain, aprende isso: X", "brain, salva: Y", "registra no brain"
    "loja_integrada_query",  # "consulta pedido", "status do pedido", "meu pedido", "rastrear pedido" — Fun Personalize
    "gap_report",            # "gaps do brain", "o que o brain não sabe", "relatório de gaps"
    "echo",                  # teste — retorna o que foi dito
]

_CLASSIFY_SYSTEM = """Classifique a mensagem do Mauro em uma dessas intencoes: status_report, status_mrr, chat, create_note, activate_agent, weekly_briefing, onboard_client, brain_query, brain_ingest, loja_integrada_query, gap_report, echo

REGRAS DE CLASSIFICACAO:
- status_mrr: menciona MRR, faturamento, quanto fatura, receita mensal
- create_note: comeca ou contem "anota", "lembra que", "registra", "salva isso"
- status_report: pergunta sobre agentes, status do sistema, tasks pendentes
- chat: conversa livre, saudacoes, perguntas sobre clientes, duvidas, qualquer outra coisa
- activate_agent: ativa @agente para fazer algo
- weekly_briefing: resumo da semana, o que rolou essa semana
- onboard_client: "onborda", "onboard", "configura zenya para", "cria cliente", "novo cliente zenya" — extrai params: business_name, site_url, business_type, phone
- brain_query: "brain", "o que voce sabe sobre", "consulta o brain", "o que o brain sabe", "brain me fala" — extrai param: query (o que quer saber)
- brain_ingest: "brain, aprende", "brain, salva", "brain, registra", "ensina o brain", "adiciona ao brain", "aprende isso" — extrai param: content (o conteudo a salvar)
- loja_integrada_query: "consulta pedido", "status do pedido", "meu pedido", "rastrear pedido", "onde esta meu pedido", "situacao do pedido", "acompanhar pedido" — extrai params: cpf, email ou pedido_id conforme disponivel no texto
- gap_report: "gaps do brain", "o que o brain nao sabe", "relatorio de gaps", "brain tem gaps", "quais gaps do brain", "o que falta no brain", "lacunas do brain"
- echo: apenas para testes com a palavra "echo"

IMPORTANTE: Responda APENAS com JSON valido, sem blocos de codigo, sem markdown.
Formato: {"intent": "<intent>", "params": {}, "summary": "<1 linha resumindo o pedido>"}

Para onboard_client, extraia params do texto:
{"intent": "onboard_client", "params": {"business_name": "X", "site_url": "url", "business_type": "tipo", "phone": "55..."}, "summary": "Onboarding X"}

Para brain_query, extraia params do texto:
{"intent": "brain_query", "params": {"query": "o que o usuário quer saber"}, "summary": "Brain query: <tema>"}

Para brain_ingest, extraia params do texto:
{"intent": "brain_ingest", "params": {"content": "o conteúdo a salvar"}, "summary": "Brain ingest: <tema>"}

Para loja_integrada_query, extraia params do texto (apenas os que estiverem presentes):
{"intent": "loja_integrada_query", "params": {"cpf": "XXX.XXX.XXX-XX", "email": "x@x.com", "pedido_id": "12345"}, "summary": "Consulta pedido: <identificador>"}"""


async def classify_and_dispatch(
    text: str,
    from_number: str = "",
    task_id: Optional[str] = None,
) -> dict:
    """
    Classify intent from text and insert a runtime_task.
    Returns the created task record.
    """
    raw = await call_claude(
        prompt=text,
        system=_CLASSIFY_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=settings.sparkle_internal_client_id,
        task_id=task_id,
        agent_id="friday",
        purpose="friday_intent_classify",
        max_tokens=256,
    )

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = {"intent": "chat", "params": {}, "summary": text[:200]}

    intent: str = parsed.get("intent", "chat")
    params: dict = parsed.get("params", {})
    summary: str = parsed.get("summary", text[:200])

    if intent not in INTENTS:
        intent = "chat"

    task_payload = {
        "original_text": text,
        "intent": intent,
        "params": params,
        "summary": summary,
        "from_number": from_number,
    }

    if intent == "onboard_client" and params:
        task_payload.update(params)

    if intent == "brain_query" and params.get("query"):
        task_payload["query"] = params["query"]

    if intent == "brain_ingest" and params.get("content"):
        task_payload["content"] = params["content"]

    if intent == "loja_integrada_query" and params:
        # Promover cpf / email / pedido_id para o topo do payload
        for key in ("cpf", "email", "pedido_id"):
            if params.get(key):
                task_payload[key] = params[key]

    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": intent,
            "payload": task_payload,
            "status": "pending",
            "priority": 7,
        }).execute()
    )

    return task.data[0] if task.data else {}
