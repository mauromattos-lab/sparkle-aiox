"""
activate_agent handler — executa subagent real via Claude API tool_use.

Quando Mauro diz "ativa o @analyst pra analisar X":
  1. Valida o agente em _AVAILABLE_AGENTS
  2. Monta contexto (Brain + request)
  3. Executa subagent loop com tool_use (brain_query, supabase_read, web_search, calculate)
  4. Retorna analise real com custo registrado

Seguranca: 7 camadas de isolamento (whitelist tools, whitelist tables,
regex calculate, sem filesystem/shell, max iterations, timeout, read-only).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Optional

import anthropic

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.handlers.brain_query import handle_brain_query
from runtime.utils.llm import _estimate_cost, _log_cost_async

# -- Anthropic client ----------------------------------------------------------

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# -- Agent registry -------------------------------------------------------------

_ANALYST_SYSTEM = (
    "Voce e o @analyst da Sparkle AIOX -- analista de dados, mercado e performance.\n\n"
    "Seu papel:\n"
    "- Analisar dados de clientes, campanhas, MRR e performance\n"
    "- Pesquisar mercado, concorrentes e tendencias\n"
    "- Gerar insights acionaveis com base em dados reais\n"
    "- Sempre fundamentar analises em numeros e evidencias\n\n"
    "Ferramentas disponiveis:\n"
    "- brain_query: consulta a base de conhecimento da Sparkle (Brain)\n"
    "- supabase_read: le dados do banco de dados (SELECT apenas)\n"
    "- web_search: pesquisa na web (se disponivel)\n"
    "- calculate: avalia expressoes matematicas\n\n"
    "Regras:\n"
    "- Sempre consulte o Brain primeiro para contexto\n"
    "- Use dados reais do Supabase quando relevante\n"
    "- Entregue no minimo 3 pontos especificos e acionaveis\n"
    "- Seja direto -- Mauro nao tem paciencia para enrolacao\n"
    "- Nunca invente dados. Se nao tem, diga.\n"
    "- Responda em portugues brasileiro"
)

_DEV_SYSTEM = (
    "Voce e o @dev da Sparkle AIOX -- desenvolvedor full-stack e engenheiro de infraestrutura.\n\n"
    "Seu papel:\n"
    "- Analisar codigo, arquitetura e infraestrutura existente\n"
    "- Diagnosticar bugs, falhas e problemas de performance\n"
    "- Consultar dados do banco para debug e investigacao\n"
    "- Propor solucoes tecnicas fundamentadas em dados reais\n\n"
    "Ferramentas disponiveis:\n"
    "- brain_query: consulta a base de conhecimento da Sparkle (Brain)\n"
    "- supabase_read: le dados do banco de dados (SELECT apenas)\n"
    "- calculate: avalia expressoes matematicas\n\n"
    "Regras:\n"
    "- Modo READ-ONLY: voce consulta e analisa, nao faz deploy nem altera dados\n"
    "- Sempre consulte o Brain primeiro para contexto do sistema\n"
    "- Use dados reais do Supabase para fundamentar diagnosticos\n"
    "- Seja tecnico e preciso — Mauro entende codigo\n"
    "- Responda em portugues brasileiro"
)

_QA_SYSTEM = (
    "Voce e o @qa da Sparkle AIOX -- engenheiro de qualidade e validacao.\n\n"
    "Seu papel:\n"
    "- Validar entregas, funcionalidades e integridade de dados\n"
    "- Identificar edge cases, riscos e pontos de falha\n"
    "- Verificar se criterios de aceitacao foram cumpridos\n"
    "- Consultar dados do banco para validacao cruzada\n\n"
    "Ferramentas disponiveis:\n"
    "- brain_query: consulta a base de conhecimento da Sparkle (Brain)\n"
    "- supabase_read: le dados do banco de dados (SELECT apenas)\n\n"
    "Regras:\n"
    "- Modo READ-ONLY: voce valida, nao altera\n"
    "- Sempre consulte o Brain para entender o contexto esperado\n"
    "- Liste problemas encontrados com severidade (critico, alto, medio, baixo)\n"
    "- Sugira testes especificos quando relevante\n"
    "- Responda em portugues brasileiro"
)

_ARCHITECT_SYSTEM = (
    "Voce e o @architect (Aria) da Sparkle AIOX -- arquiteta de sistemas e decisoes tecnicas.\n\n"
    "Seu papel:\n"
    "- Avaliar decisoes arquiteturais e tradeoffs\n"
    "- Pesquisar padroes, tecnologias e alternativas\n"
    "- Analisar a arquitetura atual via Brain e banco de dados\n"
    "- Propor ADRs (Architecture Decision Records) fundamentadas\n\n"
    "Ferramentas disponiveis:\n"
    "- brain_query: consulta a base de conhecimento da Sparkle (Brain)\n"
    "- supabase_read: le dados do banco de dados (SELECT apenas)\n"
    "- web_search: pesquisa na web para referências e padrões\n\n"
    "Regras:\n"
    "- Sempre consulte o Brain primeiro para contexto existente\n"
    "- Fundamente decisoes em tradeoffs explicitos (custo, complexidade, manutencao)\n"
    "- Considere o contexto Sparkle: equipe pequena, MVP, custo importa\n"
    "- Responda em portugues brasileiro"
)

_PO_SYSTEM = (
    "Voce e o @po da Sparkle AIOX -- Product Owner focado em valor e prioridade.\n\n"
    "Seu papel:\n"
    "- Revisar entregas do ponto de vista de produto e usuario\n"
    "- Validar se a entrega resolve o problema do usuario\n"
    "- Priorizar backlog com base em valor vs esforco\n"
    "- Analisar dados de uso e feedback para decisoes de produto\n\n"
    "Ferramentas disponiveis:\n"
    "- brain_query: consulta a base de conhecimento da Sparkle (Brain)\n"
    "- supabase_read: le dados do banco de dados (SELECT apenas)\n\n"
    "Regras:\n"
    "- Sempre consulte o Brain para entender o historico do produto\n"
    "- Foque em valor para o usuario final, nao em tecnologia\n"
    "- Use dados reais para fundamentar priorizacao\n"
    "- Responda em portugues brasileiro"
)

_AVAILABLE_AGENTS: dict[str, dict[str, Any]] = {
    "analyst": {
        "name": "@analyst",
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "max_tool_iterations": 10,
        "timeout_s": 90,
        "system_prompt": _ANALYST_SYSTEM,
    },
    "dev": {
        "name": "@dev",
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "max_tool_iterations": 10,
        "timeout_s": 90,
        "system_prompt": _DEV_SYSTEM,
    },
    "qa": {
        "name": "@qa",
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "max_tool_iterations": 10,
        "timeout_s": 90,
        "system_prompt": _QA_SYSTEM,
    },
    "architect": {
        "name": "@architect",
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "max_tool_iterations": 10,
        "timeout_s": 90,
        "system_prompt": _ARCHITECT_SYSTEM,
    },
    "po": {
        "name": "@po",
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "max_tool_iterations": 8,
        "timeout_s": 90,
        "system_prompt": _PO_SYSTEM,
    },
}


def _normalize_agent(name: str) -> str:
    """Normalize: '@analyst' -> 'analyst', 'analyst' -> 'analyst'."""
    return name.lstrip("@").strip().lower()


# -- Tool definitions (Claude API format) ---------------------------------------

_TOOL_DEFINITIONS = [
    {
        "name": "brain_query",
        "description": (
            "Consulta a base de conhecimento da Sparkle (Brain). "
            "Use para buscar contexto sobre clientes, processos, estrategias, historico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "O que buscar no Brain (ex: 'dados do cliente Vitalis')",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "supabase_read",
        "description": (
            "Executa SELECT no banco de dados Supabase. APENAS leitura. "
            "Tabelas permitidas: clients, runtime_tasks, llm_cost_log, knowledge_base, "
            "conversation_history, agent_work_items. "
            "Use para dados quantitativos: MRR, tasks, custos, conversas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Nome da tabela (ex: 'clients', 'llm_cost_log')",
                },
                "select": {
                    "type": "string",
                    "description": "Colunas a selecionar (ex: '*', 'id,name,mrr'). Default: '*'",
                },
                "filters": {
                    "type": "object",
                    "description": "Filtros como {coluna: valor} para .eq(). Opcional.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximo de registros. Default: 20, max: 50.",
                },
                "order_by": {
                    "type": "string",
                    "description": "Coluna para ordenar (ex: 'created_at'). Opcional.",
                },
                "order_desc": {
                    "type": "boolean",
                    "description": "Ordenar desc? Default: true",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Pesquisa na web via EXA API. Use para dados de mercado, "
            "concorrentes, tendencias, informacoes externas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca (ex: 'mercado IA WhatsApp Brasil 2026')",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate",
        "description": (
            "Avalia expressoes matematicas. Use para calculos de MRR, ROI, "
            "percentuais, projecoes. Apenas numeros e operadores (+, -, *, /, %, ())."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expressao matematica (ex: '4594 * 1.15', '(500 + 650) / 2')",
                }
            },
            "required": ["expression"],
        },
    },
]


# -- Tool executors -------------------------------------------------------------

_SUPABASE_TABLE_WHITELIST = {
    "clients", "runtime_tasks", "llm_cost_log",
    "knowledge_base", "conversation_history", "agent_work_items",
    "zenya_clients", "gap_reports",
}

_CALCULATE_PATTERN = re.compile(r"^[\d\s+\-*/().,%]+$")


async def _exec_brain_query(params: dict) -> str:
    """Reutiliza o handle_brain_query existente."""
    query = params.get("query", "")
    if not query:
        return "Erro: query vazia."
    fake_task = {"payload": {"query": query}, "id": None}
    result = await handle_brain_query(fake_task)
    return result.get("message", "Sem resultado do Brain.")


async def _exec_supabase_read(params: dict) -> str:
    """SELECT com whitelist de tabelas."""
    table = params.get("table", "")
    if table not in _SUPABASE_TABLE_WHITELIST:
        allowed = ", ".join(sorted(_SUPABASE_TABLE_WHITELIST))
        return f"Erro: tabela '{table}' nao permitida. Tabelas disponiveis: {allowed}"

    select = params.get("select", "*")
    filters = params.get("filters", {})
    limit = min(params.get("limit", 20), 50)
    order_by = params.get("order_by")
    order_desc = params.get("order_desc", True)

    try:
        query = supabase.table(table).select(select)
        if isinstance(filters, dict):
            for col, val in filters.items():
                query = query.eq(col, val)
        if order_by:
            query = query.order(order_by, desc=order_desc)
        query = query.limit(limit)
        result = await asyncio.to_thread(lambda: query.execute())
        data = result.data or []
        if not data:
            return f"Nenhum registro encontrado em '{table}' com os filtros aplicados."
        text = json.dumps(data, default=str, ensure_ascii=False)
        if len(text) > 8000:
            text = text[:8000] + "\n... (truncado)"
        return text
    except Exception as e:
        return f"Erro ao consultar '{table}': {e}"


async def _exec_web_search(params: dict) -> str:
    """EXA API search. Graceful fallback se sem key."""
    query = params.get("query", "")
    if not query:
        return "Erro: query vazia."

    exa_key = os.getenv("EXA_API_KEY", "")
    if not exa_key:
        return (
            "web_search indisponivel: EXA_API_KEY nao configurada. "
            "Use brain_query e supabase_read para dados internos."
        )

    try:
        import httpx
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": exa_key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "num_results": 5,
                    "use_autoprompt": True,
                    "type": "neural",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return f"Nenhum resultado encontrado para: {query}"
            lines = []
            for r in results[:5]:
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("text", "")[:300]
                lines.append(f"- {title}\n  {url}\n  {snippet}")
            return "\n\n".join(lines)
    except Exception as e:
        return f"Erro na busca web: {e}"


async def _exec_calculate(params: dict) -> str:
    """eval com sandbox rigido: apenas numeros e operadores."""
    expression = params.get("expression", "")
    if not expression:
        return "Erro: expressao vazia."

    # Remove commas (thousand separators in PT-BR)
    clean = expression.replace(",", ".")

    if not _CALCULATE_PATTERN.match(clean.replace(".", "")):
        return (
            f"Erro: expressao contem caracteres nao permitidos. "
            f"Apenas numeros e operadores (+, -, *, /, %, ()). Recebido: {expression}"
        )

    try:
        result = eval(clean, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Erro no calculo: {e}"


# Tool name -> executor
_TOOL_EXECUTORS: dict[str, Any] = {
    "brain_query": _exec_brain_query,
    "supabase_read": _exec_supabase_read,
    "web_search": _exec_web_search,
    "calculate": _exec_calculate,
}


# -- Subagent loop --------------------------------------------------------------

async def _run_subagent(
    agent_config: dict,
    user_prompt: str,
    task_id: Optional[str] = None,
    agent_key: Optional[str] = None,
) -> tuple[str, list[str], float]:
    """
    Executa o subagent com tool_use loop.
    Retorna (texto_final, ferramentas_usadas, custo_total_usd).

    SYS-2.5: monta contexto dinamico via assembler (blocos do banco + estado ao vivo).
    Fallback para system_prompt hardcoded se assembler falhar.
    """
    model = agent_config["model"]
    max_tokens = agent_config["max_tokens"]
    max_iterations = agent_config["max_tool_iterations"]

    # SYS-2.5: Context Assembly — base_prompt + contexto dinamico
    base_system = agent_config["system_prompt"]
    if agent_key:
        try:
            from runtime.context.assembler import assemble_context
            dynamic_context = await assemble_context(agent_key, user_prompt)
            if dynamic_context:
                system = f"{base_system}\n\n{dynamic_context}"
            else:
                system = base_system
        except Exception as e:
            print(f"[activate_agent] context assembler falhou, usando fallback: {e}")
            system = base_system
    else:
        system = base_system

    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    tools_used: list[str] = []
    total_cost = 0.0
    final_text = "Analise concluida sem texto."
    response = None

    for iteration in range(max_iterations):
        response = await _client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=_TOOL_DEFINITIONS,
            max_tokens=max_tokens,
        )

        # Accumulate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = _estimate_cost(model, input_tokens, output_tokens)
        total_cost += cost

        # Log cost per iteration (fire-and-forget)
        asyncio.create_task(_log_cost_async(
            client_id=settings.sparkle_internal_client_id,
            task_id=task_id,
            agent_id=agent_key or "analyst",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            purpose=f"{agent_key or 'agent'}_execution",
        ))

        # Check for tool_use blocks
        tool_calls = [b for b in response.content if b.type == "tool_use"]

        if not tool_calls:
            # Final response -- extract text
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            final_text = "\n".join(text_blocks) if text_blocks else "Analise concluida sem texto."
            break

        # Execute tools and build results
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tc in tool_calls:
            tool_name = tc.name
            if tool_name not in _TOOL_EXECUTORS:
                result_str = f"Erro: ferramenta '{tool_name}' nao disponivel."
            else:
                tools_used.append(tool_name)
                print(f"[activate_agent] iter={iteration} tool={tool_name} input={tc.input}")
                result_str = await _TOOL_EXECUTORS[tool_name](tc.input)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result_str,
            })
        messages.append({"role": "user", "content": tool_results})
    else:
        # Exhausted iterations -- grab whatever text is in the last response
        if response is not None:
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            if text_blocks:
                final_text = "\n".join(text_blocks)

    return (final_text, tools_used, total_cost)


# -- Main handler ---------------------------------------------------------------

# Known agents (includes non-subagent ones for validation)
_KNOWN_AGENTS = {
    "@dev", "@qa", "@architect", "@analyst",
    "@pm", "@po", "@sm", "@squad-creator", "@devops",
}


async def handle_activate_agent(task: dict) -> dict:
    """
    Ativa um subagent real via Claude API com tool_use.
    Se o agente nao tem subagent implementado, retorna lista de disponiveis.
    """
    payload = task.get("payload", {})

    agent_raw = _extract_agent(payload)
    request = _extract_request(payload)

    if not agent_raw:
        return {
            "message": (
                "Nao identifiquei qual agente voce quer acionar. "
                "Exemplo: 'ativa o @analyst pra analisar o cliente Vitalis'"
            )
        }

    agent_key = _normalize_agent(agent_raw)
    agent_display = f"@{agent_key}"

    # Check if agent has real subagent implementation
    if agent_key in _AVAILABLE_AGENTS:
        return await _execute_subagent(agent_key, request, task)

    # Agent exists but no subagent yet
    if agent_raw in _KNOWN_AGENTS or agent_display in _KNOWN_AGENTS:
        available = ", ".join(f"@{k}" for k in sorted(_AVAILABLE_AGENTS.keys()))
        return {
            "message": (
                f"{agent_display} ainda nao tem execucao autonoma implementada. "
                f"Agentes disponiveis para ativacao real: {available}. "
                f"Os demais estao disponiveis via Claude Code."
            ),
            "agent": agent_display,
            "request": request,
        }

    # Unknown agent
    available = ", ".join(f"@{k}" for k in sorted(_AVAILABLE_AGENTS.keys()))
    known = ", ".join(sorted(_KNOWN_AGENTS))
    return {
        "message": (
            f"Agente '{agent_display}' nao reconhecido. "
            f"Agentes disponiveis: {available} (execucao real) e {known} (via Claude Code)."
        )
    }


async def _execute_subagent(agent_key: str, request: str, task: dict) -> dict:
    """Executa o subagent com timeout e trata erros."""
    config = _AVAILABLE_AGENTS[agent_key]
    task_id = task.get("id")
    agent_display = config["name"]
    timeout = config["timeout_s"]

    if not request:
        return {
            "message": (
                f"{agent_display} ativado, mas sem tarefa especifica. "
                f"Exemplo: 'ativa o {agent_display} pra analisar o desempenho do cliente Vitalis'"
            ),
            "agent": agent_display,
        }

    # Build user prompt
    user_prompt = f"Tarefa solicitada pelo Mauro: {request}"

    try:
        text, tools_used, total_cost = await asyncio.wait_for(
            _run_subagent(config, user_prompt, task_id, agent_key=agent_key),
            timeout=timeout,
        )

        return {
            "message": f"{agent_display}:\n\n{text}",
            "agent": agent_display,
            "request": request,
            "tools_used": list(set(tools_used)),
            "total_cost_usd": round(total_cost, 6),
            "iterations": len(tools_used),
        }
    except asyncio.TimeoutError:
        return {
            "message": (
                f"{agent_display}: analise excedeu o tempo limite de {timeout}s. "
                f"Tente uma pergunta mais especifica."
            ),
            "agent": agent_display,
            "request": request,
            "error": "timeout",
        }
    except Exception as e:
        print(f"[activate_agent] subagent error: {e}")
        return {
            "message": f"{agent_display}: erro durante execucao -- {str(e)[:200]}",
            "agent": agent_display,
            "request": request,
            "error": str(e)[:500],
        }


# -- Helpers --------------------------------------------------------------------

def _extract_agent(payload: dict) -> str:
    """Extrai o agente do payload."""
    if payload.get("agent"):
        return payload["agent"].strip()
    text = payload.get("original_text", "").lower()
    for agent in _KNOWN_AGENTS:
        if agent in text:
            return agent
    for key in _AVAILABLE_AGENTS:
        if f"@{key}" in text:
            return f"@{key}"
    return ""


def _extract_request(payload: dict) -> str:
    """Extrai a descricao da tarefa do payload."""
    if payload.get("request"):
        return payload["request"].strip()
    text = payload.get("original_text", "")
    if not text:
        return ""
    clean = re.sub(
        r"\b(ativa|ative|chama|chame|aciona|acione|o|a|pra|para|fazer|faz)\b",
        " ", text, flags=re.IGNORECASE,
    )
    all_agents = _KNOWN_AGENTS | {f"@{k}" for k in _AVAILABLE_AGENTS}
    for agent in all_agents:
        clean = re.sub(re.escape(agent), "", clean, flags=re.IGNORECASE)
    return " ".join(clean.split()).strip()
