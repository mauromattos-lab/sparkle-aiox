"""
Context Assembler — SYS-2.5: monta contexto dinamico completo para agentes.

Combina 4 camadas (do mais estavel ao mais volatil):
  1. SISTEMA — blocos estaticos (identidade, regras, agentes, tools)
  2. PROCESSOS — processos operacionais + bootstrap do agente
  3. ESTADO — dados ao vivo (clientes, sprint items, recent tasks, capabilities, datetime)
  4. CONHECIMENTO — DNA do agente + narrativas do Brain + Brain search relevante ao request

Busca blocos da tabela agent_context_blocks (globais + especificos do agente).
Trunca camada 4 primeiro se ultrapassar MAX_CONTEXT_TOKENS.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from runtime.config import settings
from runtime.db import supabase

MAX_CONTEXT_TOKENS = 4000
# Estimativa grosseira: 1 token ~ 4 chars
_CHARS_PER_TOKEN = 4


# ── Block fetching ────────────────────────────────────────────

async def _get_blocks(layer: str, agent_id: str) -> list[dict]:
    """
    Busca blocos do banco: globais (agent_id IS NULL) + especificos do agente.
    Ordenados por priority (menor = primeiro).
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("agent_context_blocks")
            .select("block_key,content,priority")
            .eq("layer", layer)
            .eq("active", True)
            .or_(f"agent_id.is.null,agent_id.eq.{agent_id}")
            .order("priority")
            .execute()
        )
        return [
            {"title": r["block_key"], "content": r["content"]}
            for r in (result.data or [])
        ]
    except Exception as e:
        print(f"[context] falha ao buscar blocos layer={layer}: {e}")
        return []


# ── Camada 3: Estado dinamico ─────────────────────────────────

async def _build_state_context(agent_id: str) -> dict:
    """Monta contexto de estado atual do sistema — queries ao vivo."""
    parts = []

    # Datetime Brasilia
    try:
        now_brasilia = datetime.now(ZoneInfo("America/Sao_Paulo"))
        parts.append(f"Data/hora: {now_brasilia.strftime('%d/%m/%Y %H:%M')} (Brasilia)")
    except Exception:
        parts.append("Data/hora: indisponivel")

    # Clientes ativos (compacto)
    try:
        clients = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("name,type,mrr,status")
            .eq("status", "active")
            .execute()
        )
        clients_list = clients.data or []
        if clients_list:
            total_mrr = sum(c.get("mrr", 0) or 0 for c in clients_list)
            names = [c["name"] for c in clients_list]
            parts.append(
                f"Clientes ativos ({len(clients_list)}): {', '.join(names)}. "
                f"MRR total: R${total_mrr}/mes"
            )
    except Exception as e:
        print(f"[context] falha ao buscar clientes: {e}")

    # Sprint items ativos (compacto — top 8)
    try:
        items = await asyncio.to_thread(
            lambda: supabase.table("agent_work_items")
            .select("sprint_item,status,agent_id")
            .neq("status", "done")
            .order("created_at", desc=True)
            .limit(8)
            .execute()
        )
        items_list = items.data or []
        if items_list:
            items_text = "; ".join(
                f"{i['sprint_item']}={i['status']}"
                for i in items_list
            )
            parts.append(f"Sprint ativo: {items_text}")
    except Exception as e:
        print(f"[context] falha ao buscar sprint items: {e}")

    # Recent tasks (ultimas 5 tasks executadas — o que o Runtime fez)
    try:
        tasks = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("task_type,status,agent_id,created_at")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        tasks_list = tasks.data or []
        if tasks_list:
            tasks_text = "; ".join(
                f"{t['task_type']}({t.get('agent_id', '?')})={t['status']}"
                for t in tasks_list
            )
            parts.append(f"Tasks recentes: {tasks_text}")
    except Exception as e:
        print(f"[context] falha ao buscar tasks recentes: {e}")

    # Runtime capabilities (hardcoded — muda raramente, mais eficiente que query)
    parts.append(
        "Capabilities do Runtime: brain_query, brain_ingest, activate_agent, "
        "generate_content, echo, schedule_task, gap_report, workflow_execute"
    )

    return {"title": "Estado Atual", "content": "\n".join(parts)}


# ── Camada 4: Conhecimento (DNA + Brain search) ──────────────

async def _build_knowledge_context(agent_id: str, request: str) -> dict:
    """Busca DNA do agente + conhecimento do Brain relevante ao request."""
    content_parts = []

    # DNA do agente
    try:
        dna = await asyncio.to_thread(
            lambda: supabase.table("agent_dna")
            .select("layer,content")
            .eq("agent_id", agent_id)
            .eq("active", True)
            .limit(10)
            .execute()
        )
        if dna.data:
            by_layer: dict[str, list[str]] = {}
            for d in dna.data:
                by_layer.setdefault(d["layer"], []).append(d["content"])
            dna_lines = []
            for layer, items in by_layer.items():
                dna_lines.append(f"{layer.title()}: {'; '.join(i[:120] for i in items)}")
            content_parts.append("DNA: " + " | ".join(dna_lines))
    except Exception as e:
        print(f"[context] falha ao buscar DNA para {agent_id}: {e}")

    # Brain knowledge search — busca chunks relevantes ao request
    if request:
        try:
            brain_chunks = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("content,source")
                .text_search("content", request, config="portuguese")
                .limit(3)
                .execute()
            )
            chunks = brain_chunks.data or []
            if chunks:
                brain_text = "\n".join(
                    f"- [{c.get('source', '?')}] {c['content'][:300]}"
                    for c in chunks
                )
                content_parts.append(f"Brain (relevante):\n{brain_text}")
        except Exception as e:
            print(f"[context] falha ao buscar Brain chunks: {e}")

    # Narrativas de entidades (top 2 — compacto)
    try:
        narratives = await asyncio.to_thread(
            lambda: supabase.table("brain_entities")
            .select("canonical_name,narrative")
            .not_.is_("narrative", "null")
            .order("updated_at", desc=True)
            .limit(2)
            .execute()
        )
        narrative_texts = [
            f"{n['canonical_name']}: {n['narrative'][:200]}"
            for n in (narratives.data or [])
            if n.get("narrative")
        ]
        if narrative_texts:
            content_parts.append("Entidades: " + " | ".join(narrative_texts))
    except Exception as e:
        print(f"[context] falha ao buscar narrativas: {e}")

    content = "\n\n".join(content_parts) if content_parts else ""
    return {"title": "Conhecimento (Brain)", "content": content}


# ── Truncamento inteligente ───────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """Estimativa grosseira de tokens (1 token ~ 4 chars)."""
    return len(text) // _CHARS_PER_TOKEN


def _truncate_if_needed(full_context: str, max_tokens: int) -> str:
    """
    Trunca se necessario. Preserva camadas 1 e 2 integrais.
    Corta do final (camada 4 = conhecimento, mais volatil).
    """
    estimated = _estimate_tokens(full_context)
    if estimated <= max_tokens:
        return full_context

    max_chars = max_tokens * _CHARS_PER_TOKEN
    if len(full_context) > max_chars:
        truncated = full_context[:max_chars]
        # Tenta cortar em boundary limpo (final de secao)
        last_separator = truncated.rfind("\n\n---\n\n")
        if last_separator > max_chars * 0.7:
            truncated = truncated[:last_separator]
        return truncated + "\n\n[contexto truncado por limite de tokens]"

    return full_context


# ── API publica ───────────────────────────────────────────────

async def assemble_context(agent_id: str, request: str = "") -> str:
    """
    Monta o contexto completo para um agente.
    Combina blocos estaticos (Supabase) + dados dinamicos (queries ao vivo).

    Retorna string formatada para ser concatenada ao system prompt base do agente.
    Em caso de falha total, retorna string vazia (fallback para system_prompt hardcoded).
    """
    try:
        blocks: list[dict] = []

        # Fetch all layers in parallel for speed
        (system_blocks, process_blocks, state, knowledge) = await asyncio.gather(
            _get_blocks(layer="system", agent_id=agent_id),
            _get_blocks(layer="process", agent_id=agent_id),
            _build_state_context(agent_id),
            _build_knowledge_context(agent_id, request),
        )

        # CAMADA 1: SISTEMA
        blocks.extend(system_blocks)

        # CAMADA 2: PROCESSOS
        blocks.extend(process_blocks)

        # CAMADA 3: ESTADO
        blocks.append(state)

        # CAMADA 4: CONHECIMENTO
        if knowledge.get("content"):
            blocks.append(knowledge)

        if not blocks:
            return ""

        # Monta texto final com headers de secao
        sections = []
        for block in blocks:
            if block.get("content"):
                sections.append(f"## {block['title']}\n{block['content']}")

        full_context = "\n\n---\n\n".join(sections)

        # Trunca se necessario (preserva camadas 1 e 2 integrais)
        return _truncate_if_needed(full_context, MAX_CONTEXT_TOKENS)

    except Exception as e:
        print(f"[context] falha ao montar contexto para {agent_id}: {e}")
        return ""
