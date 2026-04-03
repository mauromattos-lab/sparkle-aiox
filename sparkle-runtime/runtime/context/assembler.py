"""
Context Assembler — SYS-2.2: monta contexto completo para agentes.

Combina 4 camadas (do mais estavel ao mais volatil):
  1. SISTEMA — blocos estaticos (identidade, regras, agentes, tools)
  2. PROCESSOS — processos operacionais + bootstrap do agente
  3. ESTADO — dados ao vivo (clientes, sprint items, datetime)
  4. CONHECIMENTO — DNA do agente + narrativas do Brain

Busca blocos da tabela agent_context_blocks (globais + especificos do agente).
Trunca camada 4 primeiro se ultrapassar MAX_CONTEXT_TOKENS.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from runtime.config import settings
from runtime.db import supabase

MAX_CONTEXT_TOKENS = 12000
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

async def _build_state_context() -> dict:
    """Monta contexto de estado atual do sistema — queries ao vivo."""
    parts = []

    # Datetime Brasilia
    try:
        now_brasilia = datetime.now(ZoneInfo("America/Sao_Paulo"))
        parts.append(f"Data/hora: {now_brasilia.strftime('%d/%m/%Y %H:%M')} (Brasilia)")
    except Exception:
        parts.append("Data/hora: indisponivel")

    # Clientes ativos
    try:
        clients = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("name,type,mrr,status")
            .eq("status", "active")
            .execute()
        )
        clients_list = clients.data or []
        if clients_list:
            clients_text = "\n".join(
                f"- {c['name']} ({c.get('type', '?')}): R${c.get('mrr', 0)}/mes — {c['status']}"
                for c in clients_list
            )
            parts.append(f"Clientes ativos:\n{clients_text}")
        else:
            parts.append("Clientes ativos: nenhum no banco")
    except Exception as e:
        print(f"[context] falha ao buscar clientes: {e}")
        parts.append("Clientes ativos: consulta falhou")

    # Sprint items ativos
    try:
        items = await asyncio.to_thread(
            lambda: supabase.table("agent_work_items")
            .select("sprint_item,status,agent_id,notes")
            .neq("status", "done")
            .order("created_at", desc=True)
            .limit(15)
            .execute()
        )
        items_list = items.data or []
        if items_list:
            items_text = "\n".join(
                f"- {i['sprint_item']}: {i['status']} ({i.get('agent_id', '?')})"
                for i in items_list
            )
            parts.append(f"Items de sprint em andamento:\n{items_text}")
        else:
            parts.append("Items de sprint: nenhum item ativo")
    except Exception as e:
        print(f"[context] falha ao buscar sprint items: {e}")
        parts.append("Sprint items: consulta falhou")

    return {"title": "Estado Atual do Sistema", "content": "\n\n".join(parts)}


# ── Camada 4: Conhecimento (DNA + Narrativas) ────────────────

async def _build_knowledge_context(agent_id: str, request: str) -> dict:
    """Busca DNA do agente + narrativas relevantes do Brain."""
    content_parts = []

    # DNA do agente
    try:
        dna = await asyncio.to_thread(
            lambda: supabase.table("agent_dna")
            .select("layer,content")
            .eq("agent_id", agent_id)
            .eq("active", True)
            .limit(20)
            .execute()
        )
        if dna.data:
            by_layer: dict[str, list[str]] = {}
            for d in dna.data:
                by_layer.setdefault(d["layer"], []).append(d["content"])
            dna_text = ""
            for layer, items in by_layer.items():
                dna_text += f"\n### {layer.title()}\n"
                for item in items:
                    dna_text += f"- {item}\n"
            content_parts.append(f"DNA do Agente:\n{dna_text}")
    except Exception as e:
        print(f"[context] falha ao buscar DNA para {agent_id}: {e}")

    # Narrativas de entidades (top 3 mais recentes)
    try:
        narratives = await asyncio.to_thread(
            lambda: supabase.table("brain_entities")
            .select("canonical_name,narrative")
            .not_.is_("narrative", "null")
            .order("updated_at", desc=True)
            .limit(3)
            .execute()
        )
        narrative_texts = [
            f"**{n['canonical_name']}:** {n['narrative'][:500]}"
            for n in (narratives.data or [])
            if n.get("narrative")
        ]
        if narrative_texts:
            content_parts.append(
                f"Entidades Conhecidas:\n\n" + "\n\n".join(narrative_texts)
            )
    except Exception as e:
        print(f"[context] falha ao buscar narrativas: {e}")

    content = "\n\n".join(content_parts) if content_parts else "Sem DNA ou narrativas carregados."
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

        # CAMADA 1: SISTEMA — blocos estaticos do banco
        system_blocks = await _get_blocks(layer="system", agent_id=agent_id)
        blocks.extend(system_blocks)

        # CAMADA 2: PROCESSOS — blocos filtrados por agente
        process_blocks = await _get_blocks(layer="process", agent_id=agent_id)
        blocks.extend(process_blocks)

        # CAMADA 3: ESTADO — montado dinamicamente
        state = await _build_state_context()
        blocks.append(state)

        # CAMADA 4: CONHECIMENTO — DNA + narrativas
        knowledge = await _build_knowledge_context(agent_id, request)
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
