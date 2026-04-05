"""
Onboarding — ONB-2: Templates de perguntas por vertical.

Maximo 8 perguntas por template (benchmark: mais que isso a taxa de completude cai de 70% para 20%).
Templates são configuráveis aqui — não hardcoded nos handlers.
"""
from __future__ import annotations

from typing import Optional


# ── Templates por vertical ─────────────────────────────────────

TEMPLATES: dict[str, list[str]] = {
    "confeitaria": [
        "Qual o horário de funcionamento e entrega?",
        "Quais os 3 produtos mais vendidos?",
        "Você trabalha com encomendas? Qual o prazo mínimo?",
        "Tem cardápio digital ou tabela de preços? (se sim, pode enviar aqui)",
        "Qual pergunta os clientes SEMPRE fazem?",
        "Faz entrega própria ou usa app (iFood, Rappi etc)?",
    ],
    "gastronomia": [
        "Qual o horário de funcionamento e entrega?",
        "Quais os 3 produtos mais vendidos?",
        "Você trabalha com encomendas? Qual o prazo mínimo?",
        "Tem cardápio digital ou tabela de preços? (se sim, pode enviar aqui)",
        "Qual pergunta os clientes SEMPRE fazem?",
        "Faz entrega própria ou usa app (iFood, Rappi etc)?",
    ],
    "saude": [
        "Qual o horário de atendimento?",
        "Quais os 3 serviços mais procurados?",
        "Aceita convênio/plano? Quais?",
        "Como funciona o agendamento hoje?",
        "Qual pergunta os clientes SEMPRE fazem?",
    ],
    "estetica": [
        "Qual o horário de atendimento?",
        "Quais os 3 serviços mais procurados?",
        "Aceita convênio/plano? Quais?",
        "Como funciona o agendamento hoje?",
        "Qual pergunta os clientes SEMPRE fazem?",
    ],
    "otica": [
        "Qual o horário de atendimento?",
        "Quais os 3 serviços mais procurados?",
        "Aceita convênio/plano? Quais?",
        "Como funciona o agendamento hoje?",
        "Qual pergunta os clientes SEMPRE fazem?",
    ],
    "educacao": [
        "Qual o horário de funcionamento e atendimento?",
        "Quais cursos/séries você oferece?",
        "Como funciona a matrícula?",
        "Qual o canal principal de comunicação com pais/alunos?",
        "Qual pergunta os pais SEMPRE fazem?",
    ],
    "ecommerce": [
        "Quais os 3 produtos mais vendidos?",
        "Qual o prazo médio de entrega?",
        "Aceita troca/devolução? Como funciona?",
        "Quais formas de pagamento aceita?",
        "Qual pergunta os clientes SEMPRE fazem no WhatsApp?",
    ],
    "generico": [
        "Qual o horário de funcionamento do seu negócio?",
        "Quais são os 3 serviços/produtos mais procurados?",
        "Qual o diferencial do seu negócio (o que você responde quando perguntam 'por que você é diferente')?",
        "Tem alguma pergunta que os clientes SEMPRE fazem? Qual?",
        "Quando um cliente quer falar com você diretamente, como prefere ser contatado?",
    ],
}

# Aliases para normalização do business_type
_ALIASES: dict[str, str] = {
    "confeitaria": "confeitaria",
    "gastronomia": "gastronomia",
    "restaurante": "gastronomia",
    "padaria": "gastronomia",
    "saude": "saude",
    "saúde": "saude",
    "clinica": "saude",
    "clínica": "saude",
    "medico": "saude",
    "médico": "saude",
    "estetica": "estetica",
    "estética": "estetica",
    "beleza": "estetica",
    "otica": "otica",
    "ótica": "otica",
    "educacao": "educacao",
    "educação": "educacao",
    "escola": "educacao",
    "curso": "educacao",
    "ecommerce": "ecommerce",
    "e-commerce": "ecommerce",
    "loja": "ecommerce",
    "loja virtual": "ecommerce",
}


def get_questions(business_type: Optional[str]) -> list[str]:
    """
    Retorna lista de perguntas para o business_type fornecido.
    Faz lookup por alias normalizado, caindo em 'generico' se não encontrar.
    Garante máximo de 8 perguntas (benchmark PME).
    """
    if not business_type:
        return TEMPLATES["generico"]

    normalized = business_type.lower().strip()
    key = _ALIASES.get(normalized, normalized)
    questions = TEMPLATES.get(key, TEMPLATES["generico"])
    return questions[:8]  # hard cap: 8 perguntas
