"""
Onboarding — gerador de soul_prompt para Zenya do cliente.

Usa Claude Haiku (cost-efficient) para transformar DNA extraido
em um soul_prompt personalizado em portugues brasileiro.
"""
from __future__ import annotations

import json

from runtime.config import settings
from runtime.utils.llm import call_claude


_SOUL_PROMPT_SYSTEM = """Voce e um especialista em criar system prompts (soul prompts) para assistentes virtuais de atendimento ao cliente no WhatsApp.

Dado o DNA de um negocio (personalidade, tom, produtos, regras, FAQ, diferenciais, publico-alvo, objecoes), gere um soul_prompt COMPLETO para a Zenya — a assistente virtual desse negocio.

REGRAS DO SOUL PROMPT:
- Portugues brasileiro, tom amigavel e profissional
- Nome da assistente: Zenya (a menos que indicado outro nome no DNA)
- Incluir: identidade, tom de voz, fluxo de atendimento, regras criticas, como escalar para humano
- Tamanho ideal: 2.000-4.000 caracteres
- Nao inventar informacoes que nao estao no DNA — usar [PENDENTE] para dados faltantes
- Incluir exemplos de frases tipicas baseadas no tom extraido
- Incluir regras de negocio (horarios, prazos, restricoes) quando disponiveis
- Estruturar em secoes claras: IDENTIDADE, TOM, PRODUTOS/SERVICOS, REGRAS, FLUXO DE ATENDIMENTO, ESCALACAO

FORMATO: Responda APENAS com o texto do soul_prompt, sem JSON, sem markdown, sem blocos de codigo.
O texto sera usado diretamente como system prompt da IA."""


async def generate_zenya_prompt(client_id: str, dna: dict) -> str:
    """
    Gera soul_prompt personalizado a partir do DNA do cliente.

    Args:
        client_id: ID do cliente no Supabase
        dna: dict com categorias de DNA (tom, persona, regras, etc.)

    Returns:
        String com o soul_prompt gerado
    """
    # Formata DNA em texto legivel para o LLM
    dna_text_parts = []
    for category, items in dna.items():
        if not items:
            continue
        if isinstance(items, list):
            for item in items:
                title = item.get("title", item.get("key", ""))
                content = item.get("content", "")
                dna_text_parts.append(f"[{category.upper()}] {title}: {content}")
        elif isinstance(items, dict):
            for key, value in items.items():
                dna_text_parts.append(f"[{category.upper()}] {key}: {value}")
        elif isinstance(items, str):
            dna_text_parts.append(f"[{category.upper()}] {items}")

    if not dna_text_parts:
        return ""

    dna_text = "\n".join(dna_text_parts)

    prompt = f"""DNA DO NEGOCIO (client_id: {client_id}):

{dna_text}

Gere o soul_prompt completo para a Zenya deste negocio."""

    soul_prompt = await call_claude(
        prompt=prompt,
        system=_SOUL_PROMPT_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=client_id,
        task_id=f"onboarding-prompt-{client_id}",
        agent_id="onboarding",
        purpose="soul_prompt_generation",
        max_tokens=4096,
    )

    return soul_prompt.strip()
