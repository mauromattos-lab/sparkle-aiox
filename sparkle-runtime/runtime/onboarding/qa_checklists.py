"""
ONB-5: Checklists automatizados de qualidade para onboarding da Zenya.

Verifica:
- Soul prompt (AC-2.1 a AC-2.5)
- Knowledge Base / KB (AC-3.1 a AC-3.5)

Retorna resultado estruturado por checklist com pass/fail por item.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

from runtime.db import supabase


# ── Constantes ─────────────────────────────────────────────────

SOUL_PROMPT_MIN_CHARS = 800

PLACEHOLDER_PATTERNS = [
    r"exemplo",
    r"\[preencher\]",
    r"lorem ipsum",
    r"\[todo\]",
    r"\{\{[^}]+\}\}",   # {{ var }}
    r"\[pendente\]",
]

ESCALATION_KEYWORDS = [
    "encaminhar",
    "atendente humano",
    "falar com alguem",
    "falar com um humano",
    "chamar a equipe",
    "chamar nosso time",
    "acionar",
    "transferir",
    "humano",
]

GENERIC_PLACEHOLDER_RE = re.compile(
    r"(\[preencher\]|\[todo\]|\{\{|\}\}|lorem ipsum)",
    re.IGNORECASE,
)


# ── Soul Prompt Checklist ──────────────────────────────────────

async def check_soul_prompt(client_id: str) -> dict:
    """
    AC-2.1 a AC-2.5: Valida a qualidade do soul_prompt gerado.

    Returns:
        {
            "passed": bool,
            "score": int,          # numero de checks que passaram (0-5)
            "total": 5,
            "details": [{ "check": str, "passed": bool, "reason": str }]
        }
    """
    details = []

    # Buscar dados do cliente + soul_prompt
    zenya_result = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("soul_prompt_generated,business_name,client_dna")
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )
    zenya = zenya_result.data if zenya_result else None

    if not zenya:
        return {
            "passed": False,
            "score": 0,
            "total": 5,
            "details": [{
                "check": "zenya_client_exists",
                "passed": False,
                "reason": f"zenya_clients nao encontrado para client_id={client_id}",
            }],
        }

    soul_prompt = zenya.get("soul_prompt_generated") or ""
    business_name = zenya.get("business_name") or ""

    # Buscar servicos/produtos do DNA
    dna_result = await asyncio.to_thread(
        lambda: supabase.table("client_dna")
        .select("dna_type,key,content")
        .eq("client_id", client_id)
        .in_("dna_type", ["produtos", "diferenciais", "servicos"])
        .limit(20)
        .execute()
    )
    dna_items = dna_result.data or []
    dna_products = [
        item.get("content", "").lower()
        for item in dna_items
        if item.get("content")
    ]

    # AC-2.1: soul_prompt nao vazio e >= 800 chars
    sp_len = len(soul_prompt)
    ac21_passed = sp_len >= SOUL_PROMPT_MIN_CHARS
    details.append({
        "check": "AC-2.1_tamanho_minimo",
        "passed": ac21_passed,
        "reason": (
            f"soul_prompt tem {sp_len} chars "
            f"({'ok' if ac21_passed else f'minimo e {SOUL_PROMPT_MIN_CHARS}'})"
        ),
    })

    # AC-2.2: soul_prompt contem o nome do negocio
    if business_name:
        ac22_passed = business_name.lower() in soul_prompt.lower()
    else:
        ac22_passed = False
    details.append({
        "check": "AC-2.2_nome_negocio_presente",
        "passed": ac22_passed,
        "reason": (
            f"Nome '{business_name}' {'encontrado' if ac22_passed else 'NAO encontrado'} "
            "no soul_prompt"
        ),
    })

    # AC-2.3: soul_prompt contem pelo menos 1 produto/servico do DNA
    if dna_products:
        sp_lower = soul_prompt.lower()
        product_found = any(
            prod[:30] in sp_lower
            for prod in dna_products
            if len(prod) >= 5
        )
        ac23_passed = product_found
        reason_23 = (
            "Pelo menos 1 produto/servico do DNA encontrado no soul_prompt"
            if product_found
            else "Nenhum produto/servico do DNA encontrado no soul_prompt"
        )
    else:
        # Sem DNA de produtos — checar se soul_prompt menciona ao menos algo sobre servicos
        ac23_passed = len(soul_prompt) >= SOUL_PROMPT_MIN_CHARS
        reason_23 = "DNA de produtos nao disponivel — verificado apenas tamanho minimo"

    details.append({
        "check": "AC-2.3_produtos_DNA_presentes",
        "passed": ac23_passed,
        "reason": reason_23,
    })

    # AC-2.4: soul_prompt contem instrucao de escalacao
    sp_lower = soul_prompt.lower()
    escalation_found = any(kw in sp_lower for kw in ESCALATION_KEYWORDS)
    details.append({
        "check": "AC-2.4_instrucao_escalacao",
        "passed": escalation_found,
        "reason": (
            "Instrucao de escalacao encontrada"
            if escalation_found
            else "Nenhuma instrucao de escalacao encontrada (esperado: 'humano', 'encaminhar', etc.)"
        ),
    })

    # AC-2.5: soul_prompt NAO contem placeholders ou linguagem generica inaceitavel
    placeholder_match = GENERIC_PLACEHOLDER_RE.search(soul_prompt)
    ac25_passed = placeholder_match is None
    details.append({
        "check": "AC-2.5_sem_placeholders",
        "passed": ac25_passed,
        "reason": (
            "Nenhum placeholder residual encontrado"
            if ac25_passed
            else f"Placeholder encontrado: '{placeholder_match.group()}'"
        ),
    })

    score = sum(1 for d in details if d["passed"])
    passed = score == 5  # Todos os 5 checks devem passar

    return {
        "passed": passed,
        "score": score,
        "total": 5,
        "details": details,
    }


# ── KB Checklist ───────────────────────────────────────────────

async def check_kb(client_id: str) -> dict:
    """
    AC-3.1 a AC-3.5: Valida a qualidade da Knowledge Base gerada.

    Returns:
        {
            "passed": bool,
            "score": int,          # numero de checks que passaram (0-5)
            "total": 5,
            "details": [{ "check": str, "passed": bool, "reason": str }]
        }
    """
    details = []

    # Buscar KB do cliente
    kb_result = await asyncio.to_thread(
        lambda: supabase.table("zenya_knowledge_base")
        .select("id,category,item_name,description,additional_info,active")
        .eq("client_id", client_id)
        .eq("active", True)
        .execute()
    )
    kb_items = kb_result.data or []
    total_items = len(kb_items)

    # AC-3.1: KB tem >= 15 itens
    ac31_passed = total_items >= 15
    details.append({
        "check": "AC-3.1_minimo_15_itens",
        "passed": ac31_passed,
        "reason": f"KB tem {total_items} itens ({'ok' if ac31_passed else 'minimo e 15'})",
    })

    # AC-3.2: Nenhum item tem answer vazio ou < 20 chars
    short_answers = [
        item for item in kb_items
        if not item.get("description") or len(item.get("description", "")) < 20
    ]
    ac32_passed = len(short_answers) == 0
    details.append({
        "check": "AC-3.2_respostas_completas",
        "passed": ac32_passed,
        "reason": (
            "Todas as respostas tem >= 20 chars"
            if ac32_passed
            else f"{len(short_answers)} items com resposta vazia ou muito curta"
        ),
    })

    # AC-3.3: Pelo menos 1 item cobre horario de funcionamento
    horario_keywords = ["horario", "funcionamento", "atendimento", "aberto", "fecha", "hora"]
    horario_found = any(
        any(kw in (item.get("item_name") or "").lower() or kw in (item.get("description") or "").lower()
            for kw in horario_keywords)
        for item in kb_items
    )
    details.append({
        "check": "AC-3.3_cobertura_horario",
        "passed": horario_found,
        "reason": (
            "Item sobre horario de funcionamento encontrado"
            if horario_found
            else "Nenhum item de KB cobre horario de funcionamento"
        ),
    })

    # AC-3.4: Pelo menos 1 item cobre escalacao para humano
    escalation_keywords = ["humano", "atendente", "equipe", "encaminhar", "falar com"]
    escalation_found = any(
        any(kw in (item.get("item_name") or "").lower() or kw in (item.get("description") or "").lower()
            for kw in escalation_keywords)
        for item in kb_items
    )
    details.append({
        "check": "AC-3.4_cobertura_escalacao",
        "passed": escalation_found,
        "reason": (
            "Item sobre escalacao para humano encontrado"
            if escalation_found
            else "Nenhum item de KB cobre escalacao para humano"
        ),
    })

    # AC-3.5: Nenhum item tem placeholder residual
    items_with_placeholders = [
        item for item in kb_items
        if GENERIC_PLACEHOLDER_RE.search(item.get("description") or "")
        or GENERIC_PLACEHOLDER_RE.search(item.get("item_name") or "")
    ]
    ac35_passed = len(items_with_placeholders) == 0
    details.append({
        "check": "AC-3.5_sem_placeholders_KB",
        "passed": ac35_passed,
        "reason": (
            "Nenhum placeholder residual na KB"
            if ac35_passed
            else f"{len(items_with_placeholders)} items com placeholder residual"
        ),
    })

    score = sum(1 for d in details if d["passed"])
    passed = score == 5  # Todos os 5 checks devem passar

    return {
        "passed": passed,
        "score": score,
        "total": 5,
        "details": details,
        "kb_item_count": total_items,
    }
