"""
Onboarding — ONB-3: Gerador de soul_prompt a partir do DNA do cliente.

Sequência obrigatória (AC-3.1):
  DNA extraction → soul_prompt_generator (este módulo) → kb_generator

Input:
  - DNA completo (8 categorias) como lista de itens do client_dna
  - intake_summary: resumo das respostas do formulário WhatsApp
  - business_type: para carregar template de persona da vertical
  - business_name: nome do negócio para personalização

Output:
  - soul_prompt gerado (string, 800-4000 chars)
  - salvo em zenya_clients.soul_prompt_generated
"""
from __future__ import annotations

import asyncio
from typing import Optional

from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.onboarding.vertical_templates import get_persona_template


# ── Constantes ────────────────────────────────────────────────

SOUL_PROMPT_MIN_CHARS = 800
SOUL_PROMPT_MAX_CHARS = 4000

DNA_CATEGORIES = (
    "tom", "persona", "regras", "diferenciais",
    "publico_alvo", "produtos", "objecoes", "faq",
)

_SYSTEM = """Você é especialista em criar system prompts (soul prompts) para a Zenya — assistente virtual de atendimento ao cliente via WhatsApp.

Você receberá:
1. TEMPLATE DA VERTICAL: guia de comportamento para o setor do negócio
2. DNA DO NEGÓCIO: informações extraídas automaticamente (site, Instagram, formulário)
3. INTAKE SUMMARY: resumo das respostas do próprio dono do negócio

Sua tarefa: gerar um soul_prompt COMPLETO e PERSONALIZADO que transforme a Zenya na atendente perfeita desse negócio específico.

ESTRUTURA OBRIGATÓRIA DO SOUL PROMPT:
1. IDENTIDADE: Quem é a Zenya neste contexto, para qual negócio trabalha
2. TOM DE VOZ: Como deve se comunicar (baseado no DNA de tom e persona)
3. PRODUTOS E SERVIÇOS: O que o negócio oferece, como apresentar
4. REGRAS DE NEGÓCIO: Horários, políticas, restrições operacionais
5. DIFERENCIAIS: Por que este negócio é especial
6. PERGUNTAS FREQUENTES: Respostas prontas para as principais dúvidas
7. ESCALAÇÃO: Quando e como passar para atendimento humano
8. DISCLAIMER DE IA: O que responder quando perguntada se é robô

REGRAS DE QUALIDADE:
- Português brasileiro natural, adequado ao tom do negócio
- Use APENAS informações presentes no DNA e intake — não invente dados
- Para dados faltantes, use [PENDENTE] — nunca invente horários ou preços
- Mínimo 800 caracteres, máximo 4000 caracteres
- Escreva em segunda pessoa ("Você é Zenya, atendente da...")
- Sem markdown, sem blocos de código, sem JSON — apenas texto do prompt
- Inclua exemplos de frases típicas baseados no tom extraído
- O prompt deve ser copiável diretamente como system prompt de uma IA

FORMATO: Responda APENAS com o texto do soul_prompt. Sem introdução, sem conclusão."""


async def generate_soul_prompt(
    client_id: str,
    dna_items: list[dict],
    business_name: str,
    business_type: Optional[str],
    intake_summary: str = "",
    task_id: Optional[str] = None,
) -> str:
    """
    Gera soul_prompt personalizado a partir do DNA e intake do cliente.

    Args:
        client_id: ID do cliente (para logging de custos)
        dna_items: Lista de itens do client_dna (cada item tem category, key, title, content)
        business_name: Nome do negócio
        business_type: Tipo de negócio (para template de vertical)
        intake_summary: Resumo das respostas do formulário WhatsApp
        task_id: ID da task para logging

    Returns:
        soul_prompt gerado (str) — garantido entre 800 e 4000 chars quando dados suficientes
    """
    # 1. Template da vertical
    vertical_template = get_persona_template(business_type)

    # 2. Formatar DNA por categoria
    dna_by_category: dict[str, list[str]] = {}
    for item in dna_items:
        cat = item.get("dna_type") or item.get("category", "unknown")
        content = item.get("content", "")
        key = item.get("key", "")
        title = item.get("title", "")

        line = f"  [{key}] {title}: {content}" if title else f"  [{key}]: {content}"
        dna_by_category.setdefault(cat, []).append(line)

    dna_sections = []
    for cat in DNA_CATEGORIES:
        items_in_cat = dna_by_category.get(cat, [])
        if items_in_cat:
            dna_sections.append(f"{cat.upper()}:\n" + "\n".join(items_in_cat))

    # Include any unexpected categories
    for cat, items_in_cat in dna_by_category.items():
        if cat not in DNA_CATEGORIES and items_in_cat:
            dna_sections.append(f"{cat.upper()}:\n" + "\n".join(items_in_cat))

    dna_text = "\n\n".join(dna_sections) if dna_sections else "(DNA não disponível)"

    # 3. Montar prompt completo
    prompt_parts = [
        f"NEGÓCIO: {business_name}",
        f"SETOR: {business_type or 'Geral'}",
        "",
        "=== TEMPLATE DA VERTICAL ===",
        vertical_template,
        "",
        "=== DNA DO NEGÓCIO ===",
        dna_text,
    ]

    if intake_summary.strip():
        prompt_parts += [
            "",
            "=== RESPOSTAS DO FORMULÁRIO (voz do dono) ===",
            intake_summary.strip(),
        ]

    prompt_parts += [
        "",
        f"Gere o soul_prompt completo para a Zenya da {business_name}.",
    ]

    prompt = "\n".join(prompt_parts)

    # 4. Chamar LLM
    soul_prompt = await call_claude(
        prompt=prompt,
        system=_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=client_id,
        task_id=task_id or f"soul-prompt-{client_id[:12]}",
        agent_id="onboarding",
        purpose="soul_prompt_generation_v2",
        max_tokens=4096,
    )

    soul_prompt = soul_prompt.strip()

    # 5. Validação de tamanho
    if len(soul_prompt) < SOUL_PROMPT_MIN_CHARS:
        print(
            f"[soul_prompt_generator] WARN: soul_prompt muito curto "
            f"({len(soul_prompt)} chars < {SOUL_PROMPT_MIN_CHARS}). "
            f"Dados insuficientes para {client_id[:12]}."
        )
    elif len(soul_prompt) > SOUL_PROMPT_MAX_CHARS:
        print(
            f"[soul_prompt_generator] WARN: soul_prompt muito longo "
            f"({len(soul_prompt)} chars > {SOUL_PROMPT_MAX_CHARS}). Truncando."
        )
        soul_prompt = soul_prompt[:SOUL_PROMPT_MAX_CHARS]

    # Verificar ausência de placeholders residuais óbvios de template
    if "{{" in soul_prompt or "}}" in soul_prompt:
        print(
            f"[soul_prompt_generator] WARN: soul_prompt pode ter placeholders residuais "
            f"para {client_id[:12]}."
        )

    return soul_prompt


async def save_soul_prompt_to_db(client_id: str, soul_prompt: str) -> None:
    """Salva soul_prompt em zenya_clients.soul_prompt_generated."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({"soul_prompt_generated": soul_prompt})
            .eq("client_id", client_id)
            .execute()
        )
        print(
            f"[soul_prompt_generator] soul_prompt salvo para {client_id[:12]}... "
            f"({len(soul_prompt)} chars)"
        )
    except Exception as e:
        print(f"[soul_prompt_generator] ERRO ao salvar soul_prompt: {e}")
        raise


async def fetch_dna_items(client_id: str) -> list[dict]:
    """Busca itens de DNA do cliente na tabela client_dna."""
    result = await asyncio.to_thread(
        lambda: supabase.table("client_dna")
        .select("dna_type,key,title,content,confidence")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
