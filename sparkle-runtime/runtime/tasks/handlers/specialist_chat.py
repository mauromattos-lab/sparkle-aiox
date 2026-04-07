"""
specialist_chat handler — Roteia chat para agente especialista com DNA carregado.

Fluxo:
  1. Detecta domínio do payload
  2. Carrega DNA relevante do agent_dna (filtrando por layer relacionado ao domínio)
  3. Consome brain_context já injetado pelo Brain Gate (contexto do negócio)
  4. Monta system prompt especializado = persona do domínio + DNA + contexto
  5. Responde via Claude Sonnet com contexto especializado
  6. Sinaliza brain_worthy se resposta for estratégica (para auto-ingestão)
"""
from __future__ import annotations

import asyncio

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


# ---------------------------------------------------------------------------
# Personas por domínio
# ---------------------------------------------------------------------------

_DOMAIN_PERSONAS: dict[str, str] = {
    "trafego_pago": (
        "Você é especialista em tráfego pago para pequenos negócios brasileiros. "
        "Domina Meta Ads e Google Ads. Fala em termos de ROI, CPM, CTR, ROAS. "
        "Respostas diretas, com dados quando disponível. Não faz rodeios."
    ),
    "zenya_config": (
        "Você é especialista em configuração e otimização da Zenya — assistente de IA para atendimento. "
        "Conhece profundamente fluxos de conversa, qualificação de leads, integração com WhatsApp. "
        "Foco em resultado: mais conversões, menos abandono, atendimento mais rápido."
    ),
    "conteudo": (
        "Você é especialista em criação de conteúdo para Instagram e redes sociais para negócios. "
        "Entende de copywriting, ganchos, storytelling de marca, formatos (post, carrossel, stories, reels). "
        "Cria conteúdo que para o scroll e converte."
    ),
    "estrategia": (
        "Você é consultor estratégico de negócios digitais com foco em PMEs brasileiras. "
        "Analisa mercado, precificação, posicionamento e proposta de valor. "
        "Direto, pragmático, orientado a decisão."
    ),
    "financeiro": (
        "Você é especialista em gestão financeira e métricas de negócio digital. "
        "Foca em MRR, churn, LTV, CAC, fluxo de caixa. "
        "Respostas com números quando possível."
    ),
    "tech": (
        "Você é engenheiro de software especializado em sistemas de IA e automação. "
        "Stack: Python, FastAPI, Supabase, ARQ, Claude API. "
        "Respostas técnicas precisas, com código quando necessário."
    ),
    "brain_ops": (
        "Você é especialista em gestão de conhecimento e operações do Brain da Sparkle AIOX. "
        "Conhece a estrutura do agent_dna, brain_chunks, gaps e ingestão de conteúdo. "
        "Respostas precisas sobre o que foi aprendido, o que falta, e como organizar o conhecimento."
    ),
}

_DEFAULT_PERSONA = (
    "Você é assistente especializado da Sparkle AIOX. "
    "Responde com precisão e contexto real do negócio do Mauro."
)

# Layers de DNA prioritários por domínio
_DOMAIN_DNA_LAYERS: dict[str, list[str]] = {
    "trafego_pago":  ["heuristica", "framework", "metodologia"],
    "estrategia":    ["filosofia", "modelo_mental", "heuristica"],
    "conteudo":      ["framework", "heuristica", "metodologia"],
    "zenya_config":  ["framework", "metodologia"],
    "financeiro":    ["framework", "heuristica"],
    "tech":          ["metodologia", "framework"],
    "brain_ops":     ["framework", "metodologia"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_domain_dna(domain: str, limit: int = 5) -> str:
    """Carrega DNA relevante do agent_dna para enriquecer contexto do domínio."""
    layer_priority = _DOMAIN_DNA_LAYERS.get(domain, ["framework", "heuristica"])

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("agent_dna")
            .select("layer,content,entity_name")
            .in_("layer", layer_priority)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return ""
        snippets = [
            f"[{r['layer'].upper()} — {r['entity_name']}]\n{r['content'][:300]}"
            for r in rows
        ]
        return "\n\n".join(snippets)
    except Exception as e:
        print(f"[specialist_chat] falha ao carregar DNA: {e}")
        return ""


# ---------------------------------------------------------------------------
# Handler principal
# ---------------------------------------------------------------------------

async def handle_specialist_chat(task: dict) -> dict:
    payload   = task.get("payload", {})
    task_id   = task.get("id")
    client_id = task.get("client_id") or settings.sparkle_internal_client_id

    original_text: str = payload.get("original_text", "")
    domain: str        = payload.get("domain", "geral")
    summary: str       = payload.get("summary", original_text[:200])

    # 1. Persona especialista
    persona = _DOMAIN_PERSONAS.get(domain, _DEFAULT_PERSONA)

    # 2. DNA do domínio (carregado do Supabase)
    dna_context = await _load_domain_dna(domain)

    # 3. Brain context já injetado pelo Brain Gate em task["brain_context"]
    brain_ctx  = task.get("brain_context", [])
    brain_text = ""
    if brain_ctx:
        snippets   = [c.get("raw_content", c.get("content", ""))[:300] for c in brain_ctx[:4] if c]
        brain_text = "\n\n".join(s for s in snippets if s)

    # 4. Montar system prompt composto
    system_parts = [persona]
    if dna_context:
        system_parts.append(
            f"\n\nFrameworks e heurísticas relevantes (use como base):\n{dna_context}"
        )
    if brain_text:
        system_parts.append(
            f"\n\nContexto do Brain (informações específicas do negócio):\n{brain_text}"
        )
    system_parts.append(
        "\n\nResponda em português. Seja direto, preciso e orientado a ação."
    )
    system = "\n".join(system_parts)

    # 5. Gerar resposta com Sonnet especializado
    response = await call_claude(
        prompt=original_text,
        system=system,
        model="claude-sonnet-4-6",
        client_id=client_id,
        task_id=task_id,
        agent_id=f"specialist-{domain}",
        purpose="specialist_chat",
        max_tokens=800,
    )

    # 6. Brain-worthy: respostas estratégicas e densas merecem ser memorizadas
    brain_worthy = (
        domain in ("estrategia", "trafego_pago", "zenya_config")
        and len(response) > 300
    )

    return {
        "message": response,
        "domain": domain,
        "specialist": True,
        "dna_loaded": bool(dna_context),
        "brain_chunks_used": len(brain_ctx),
        "brain_worthy": brain_worthy,
        "brain_content": (
            f"[Consulta {domain}] Pergunta: {summary}\n\nResposta: {response}"
            if brain_worthy else None
        ),
    }
