"""
contract_filler.py — Story 1.2 (AC-1.1/AC-1.2)

Preenche o template de contrato com dados do cliente.

Uso:
    from runtime.onboarding.contract_filler import fill_contract
    content = fill_contract(client_data)
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# ── Constantes ────────────────────────────────────────────────

TEMPLATE_PATH = Path(__file__).parent / "templates" / "contract_template.md"

# Escopo por tier (AC-1.2 — hardcoded por plano)
TIER_SCOPE: dict[str, str] = {
    "essencial": (
        "Chat IA 24h (texto e audio), persona personalizada, "
        "escalacao para humano, Brain DNA"
    ),
    "profissional": (
        "Essencial + Agendamento, lembretes, cobranca PIX, "
        "recuperacao de leads"
    ),
    "premium": (
        "Profissional + Assistente interno, voz (Retell), "
        "multi-alerta, setup prioritario"
    ),
}

# Alias normalization para nomes de plano variantes
_PLAN_ALIASES: dict[str, str] = {
    "essential": "essencial",
    "pro": "profissional",
    "professional": "profissional",
    "prem": "premium",
}

_BUSINESS_DAYS_AHEAD = 5


def _business_days_from_today(days: int) -> str:
    """Retorna data (dd/mm/YYYY) após N dias úteis a partir de hoje."""
    current = date.today()
    added = 0
    while added < days:
        current += timedelta(days=1)
        # 0=Mon … 4=Fri — pula Sábado(5) e Domingo(6)
        if current.weekday() < 5:
            added += 1
    return current.strftime("%d/%m/%Y")


def _normalize_plan(plan: Optional[str]) -> str:
    """Normaliza nome do plano para chave em TIER_SCOPE."""
    if not plan:
        return "essencial"
    normalized = plan.lower().strip()
    return _PLAN_ALIASES.get(normalized, normalized)


def fill_contract(client_data: dict) -> str:
    """
    Preenche o template de contrato com os dados do cliente.

    client_data esperado:
        empresa          — str  (nome da empresa / cliente)
        cnpj_cpf         — str  (opcional; usa "N/I" se ausente)
        valor_mensal     — float | str
        plano            — str  (Essencial / Profissional / Premium)
        signatario_nome  — str  (nome completo do signatário)
        signatario_email — str  (email do signatário — não vai no template mas útil para log)

    Retorna o conteúdo do contrato como string Markdown preenchida.
    """
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    plan_key = _normalize_plan(client_data.get("plano") or client_data.get("plan"))
    escopo = TIER_SCOPE.get(plan_key, TIER_SCOPE["essencial"])

    # Formata valor monetário
    valor_raw = client_data.get("valor_mensal") or client_data.get("mrr_value") or 0
    try:
        valor_fmt = f"{float(valor_raw):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        valor_fmt = str(valor_raw)

    placeholders = {
        "{empresa}":         str(client_data.get("empresa") or client_data.get("client_name") or ""),
        "{cnpj_cpf}":        str(client_data.get("cnpj_cpf") or "N/I"),
        "{valor_mensal}":    valor_fmt,
        "{plano}":           plan_key.capitalize(),
        "{escopo}":          escopo,
        "{data_inicio}":     _business_days_from_today(_BUSINESS_DAYS_AHEAD),
        "{signatario_nome}": str(client_data.get("signatario_nome") or client_data.get("contact_name") or ""),
        "{signatario_email}": str(client_data.get("signatario_email") or client_data.get("email") or ""),
    }

    content = template
    for placeholder, value in placeholders.items():
        content = content.replace(placeholder, value)

    return content
