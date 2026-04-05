"""
Onboarding — ONB-3: Gerador de Knowledge Base (KB) para Zenya.

Sequência obrigatória (AC-3.2):
  soul_prompt → kb_generator (este módulo)

Input:
  - DNA do cliente (lista de itens)
  - soul_prompt já gerado (para manter consistência de tom)
  - intake_data: dados brutos do intake (respostas formulário + scraped)
  - business_type: para FAQ template da vertical

Output:
  - Lista de itens de KB (15-40 pares pergunta-resposta)
  - Salvo em zenya_knowledge_base

AC-2.6: KB gerada tem pelo menos 15 itens e no máximo 40.
AC-2.7: KB inclui FAQ genérica do nicho + FAQs do intake + regras de escalação
         + resposta para "você é um robô?"
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.onboarding.vertical_templates import get_faq_template, FAQ_UNIVERSAL


# ── Constantes ────────────────────────────────────────────────

KB_MIN_ITEMS = 15
KB_MAX_ITEMS = 40

_SYSTEM = """Você é especialista em criar Knowledge Bases (bases de conhecimento) para assistentes virtuais de atendimento ao cliente.

Você receberá:
1. SOUL PROMPT da Zenya (tom, identidade, regras)
2. DNA DO NEGÓCIO (informações extraídas)
3. INTAKE DATA (respostas do próprio dono do negócio)
4. FAQ BASE DA VERTICAL (perguntas típicas do setor)

Sua tarefa: gerar uma Knowledge Base PERSONALIZADA com pares pergunta-resposta.

REGRAS:
- Mínimo 15 pares, máximo 40 pares
- Inclua OBRIGATORIAMENTE:
  * FAQs específicas baseadas no intake data (prioridade máxima — dados reais do dono)
  * FAQs genéricas do nicho preenchidas com dados do DNA (horários, preços, produtos)
  * Regras de escalação claras (quando chamar humano)
  * Resposta para "você é um robô?" / "você é IA?"
- Use APENAS dados confirmados do DNA/intake — para dados ausentes use "[PENDENTE: descrição do dado]"
- Tom das respostas DEVE ser consistente com o soul_prompt
- Respostas devem ser diretas, úteis, entre 1-4 frases
- Não repita perguntas muito similares

FORMATO DE RESPOSTA — JSON estrito:
{
  "items": [
    {
      "category": "horarios",
      "question": "Qual o horário de funcionamento?",
      "answer": "Atendemos de segunda a sábado, das 8h às 18h.",
      "source": "intake" | "dna" | "template" | "universal",
      "confidence": 0.0-1.0
    }
  ],
  "summary": "Resumo em 1 frase da KB gerada"
}

CATEGORIAS SUGERIDAS:
- horarios: horários e dias de funcionamento
- produtos: produtos/serviços disponíveis
- precos: valores e formas de pagamento
- pedidos: como comprar/contratar/agendar
- entrega: logística e prazos
- politicas: cancelamentos, trocas, garantias
- localizacao: endereço, como chegar
- escalacao: quando e como chamar humano
- identidade: sobre a IA / sobre o negócio
- outros: qualquer outra categoria relevante

Responda APENAS com o JSON. Sem texto antes ou depois."""


def _parse_json_response(raw: str) -> dict | None:
    """Parse JSON da resposta do LLM, removendo blocos markdown se presente."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        import json
        return json.loads(cleaned)
    except Exception:
        return None


def _extract_intake_context(intake_data: dict) -> str:
    """Extrai contexto textual do intake_data para o prompt."""
    if not intake_data:
        return ""

    parts = []

    # Respostas do formulário WhatsApp
    form_answers = intake_data.get("form_answers", [])
    if form_answers:
        parts.append("=== RESPOSTAS DO FORMULÁRIO ===")
        for qa in form_answers:
            q = qa.get("question", "")
            a = qa.get("answer", "")
            if q and a:
                parts.append(f"P: {q}\nR: {a}")

    # Resumo do scraping do site
    site_summary = intake_data.get("site_summary", "")
    if site_summary:
        parts.append(f"=== SITE DO NEGÓCIO ===\n{site_summary[:800]}")

    # Bio do Instagram
    instagram_bio = intake_data.get("instagram_bio", "")
    if instagram_bio:
        parts.append(f"=== INSTAGRAM ===\n{instagram_bio[:400]}")

    # intake_summary já consolidado
    summary = intake_data.get("summary", "")
    if summary and not form_answers:  # Só usa se não tem form_answers
        parts.append(f"=== RESUMO INTAKE ===\n{summary[:600]}")

    return "\n\n".join(parts)


async def generate_kb(
    client_id: str,
    business_name: str,
    business_type: Optional[str],
    dna_items: list[dict],
    soul_prompt: str,
    intake_data: dict,
    task_id: Optional[str] = None,
) -> list[dict]:
    """
    Gera Knowledge Base personalizada para a Zenya do cliente.

    Args:
        client_id: ID do cliente
        business_name: Nome do negócio
        business_type: Tipo de negócio (para template de vertical)
        dna_items: Itens de DNA do client_dna
        soul_prompt: Soul prompt já gerado (para consistência de tom)
        intake_data: Dados do intake (form_answers, site_summary, etc.)
        task_id: ID da task para logging

    Returns:
        Lista de itens de KB prontos para inserção no banco.
        Cada item tem: category, question, answer, source, confidence
    """
    import json as json_module

    # 1. Template de FAQ da vertical
    faq_template = get_faq_template(business_type)
    faq_template_text = "\n".join(
        f"  P: {item['q']}\n  R: {item['a']}"
        for item in faq_template[:15]  # Limita para não explodir o contexto
    )

    # 2. DNA formatado
    dna_by_cat: dict[str, list[str]] = {}
    for item in dna_items:
        cat = item.get("dna_type") or item.get("category", "?")
        content = item.get("content", "")
        key = item.get("key", "")
        dna_by_cat.setdefault(cat, []).append(f"[{key}]: {content}")

    dna_lines = []
    for cat, lines in dna_by_cat.items():
        dna_lines.append(f"{cat.upper()}:\n" + "\n".join(lines))
    dna_text = "\n\n".join(dna_lines) or "(DNA não disponível)"

    # 3. Contexto do intake
    intake_context = _extract_intake_context(intake_data)

    # 4. Montar prompt
    prompt_parts = [
        f"NEGÓCIO: {business_name}",
        f"SETOR: {business_type or 'Geral'}",
        "",
        "=== SOUL PROMPT (tom de referência) ===",
        soul_prompt[:800],  # Primeiros 800 chars como referência de tom
        "",
        "=== DNA DO NEGÓCIO ===",
        dna_text,
    ]

    if intake_context.strip():
        prompt_parts += [
            "",
            intake_context,
        ]

    prompt_parts += [
        "",
        "=== FAQ BASE DA VERTICAL (preencher com dados reais acima) ===",
        faq_template_text,
        "",
        f"Gere a Knowledge Base completa para a Zenya da {business_name}.",
        "Lembre: mínimo 15 itens, máximo 40. Inclua SEMPRE resposta para 'você é um robô?'.",
    ]

    prompt = "\n".join(prompt_parts)

    # 5. Chamar LLM
    raw = await call_claude(
        prompt=prompt,
        system=_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=client_id,
        task_id=task_id or f"kb-gen-{client_id[:12]}",
        agent_id="onboarding",
        purpose="kb_generation",
        max_tokens=6000,
    )

    # 6. Parse resposta
    parsed = _parse_json_response(raw)
    if not parsed or not parsed.get("items"):
        print(f"[kb_generator] ERRO: LLM não retornou items válidos para {client_id[:12]}")
        return []

    items = parsed["items"]

    # 7. Validação e normalização
    validated = []
    seen_questions: set[str] = set()

    for item in items:
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        if not q or not a:
            continue

        # Deduplicate (fuzzy: ignore case + strip)
        q_key = q.lower().strip("?! ")
        if q_key in seen_questions:
            continue
        seen_questions.add(q_key)

        validated.append({
            "category": item.get("category", "outros"),
            "question": q,
            "answer": a,
            "source": item.get("source", "llm"),
            "confidence": float(item.get("confidence", 0.8)),
        })

        if len(validated) >= KB_MAX_ITEMS:
            break

    # 8. Verificar mínimo
    if len(validated) < KB_MIN_ITEMS:
        print(
            f"[kb_generator] WARN: apenas {len(validated)} itens gerados "
            f"(mínimo {KB_MIN_ITEMS}) para {client_id[:12]}."
        )

    print(
        f"[kb_generator] KB gerada: {len(validated)} itens "
        f"para {client_id[:12]}..."
    )

    return validated


async def save_kb_to_db(
    client_id: str,
    kb_items: list[dict],
) -> int:
    """
    Salva itens de KB em zenya_knowledge_base.

    Remove KB anterior do cliente antes de inserir nova.
    Retorna número de itens inseridos.
    """
    if not kb_items:
        return 0

    now = datetime.now(timezone.utc).isoformat()

    # 1. Deletar KB anterior para este cliente (re-extração limpa)
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_knowledge_base")
            .delete()
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[kb_generator] WARN: falha ao limpar KB anterior: {e}")

    # 2. Preparar rows para inserção
    rows = []
    for i, item in enumerate(kb_items):
        rows.append({
            "client_id": client_id,
            "category": item.get("category", "outros"),
            "item_name": item.get("question", f"item_{i+1}"),
            "description": item.get("answer", ""),
            "active": True,
            "additional_info": f"source:{item.get('source','llm')} | confidence:{item.get('confidence', 0.8):.2f}",
        })

    # 3. Inserir em batch
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_knowledge_base").insert(rows).execute()
        )
        inserted = len(result.data) if result.data else len(rows)
        print(
            f"[kb_generator] {inserted} itens de KB salvos para "
            f"{client_id[:12]}..."
        )
        return inserted
    except Exception as e:
        print(f"[kb_generator] ERRO ao salvar KB: {e}")
        raise


async def count_kb_items(client_id: str) -> int:
    """Conta quantos itens de KB existem para o cliente."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_knowledge_base")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("active", True)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0
