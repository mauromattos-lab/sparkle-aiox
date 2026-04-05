"""
ONB-5: Banco de perguntas de teste por vertical para smoke test da Zenya.

Estrutura:
- 7 perguntas genericas (todas as verticais, incluindo edge cases)
- 3 perguntas especificas por vertical
- Fallback graceful: se vertical nao tem template, usa apenas as 7 genericas

Arquivo configuravel — nao hardcode inline no handler.
"""
from __future__ import annotations

from typing import Optional


# ── Perguntas genericas (todas as verticais) ──────────────────

GENERIC_QUESTIONS: list[dict] = [
    {
        "id": "gen_01",
        "text": "Oi, tudo bem?",
        "category": "saudacao",
        "expected_behavior": "resposta_nao_vazia",
        "escalation_test": False,
    },
    {
        "id": "gen_02",
        "text": "Qual o horario de funcionamento?",
        "category": "horarios",
        "expected_behavior": "resposta_nao_vazia",
        "escalation_test": False,
    },
    {
        "id": "gen_03",
        "text": "Onde fica voces?",
        "category": "localizacao",
        "expected_behavior": "resposta_nao_vazia",
        "escalation_test": False,
    },
    {
        "id": "gen_04",
        "text": "Quero falar com alguem",
        "category": "escalacao",
        "expected_behavior": "escalacao_presente",
        "escalation_test": True,
    },
    {
        "id": "gen_05",
        "text": "Voce e um robo?",
        "category": "identidade",
        "expected_behavior": "identidade_zenya",
        "escalation_test": False,
    },
    {
        "id": "gen_06",
        "text": "",
        "category": "edge_case",
        "expected_behavior": "graceful_empty",
        "escalation_test": False,
    },
    {
        "id": "gen_07",
        "text": "Obrigado!",
        "category": "encerramento",
        "expected_behavior": "resposta_nao_vazia",
        "escalation_test": False,
    },
]

# ── Perguntas especificas por vertical ────────────────────────

VERTICAL_QUESTIONS: dict[str, list[dict]] = {
    "confeitaria": [
        {
            "id": "conf_01",
            "text": "Tem bolo de aniversario?",
            "category": "produtos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "conf_02",
            "text": "Qual o prazo para encomenda?",
            "category": "pedidos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "conf_03",
            "text": "Aceita cartao?",
            "category": "pagamento",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "gastronomia": [
        {
            "id": "gast_01",
            "text": "Fazem delivery?",
            "category": "entrega",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "gast_02",
            "text": "Tem cardapio disponivel?",
            "category": "produtos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "gast_03",
            "text": "Qual o tempo de espera?",
            "category": "pedidos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "saude": [
        {
            "id": "saude_01",
            "text": "Como faco para agendar?",
            "category": "agendamento",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "saude_02",
            "text": "Aceita convenio?",
            "category": "convenio",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "saude_03",
            "text": "Qual o valor da consulta?",
            "category": "precos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "estetica": [
        {
            "id": "est_01",
            "text": "Como faco para agendar?",
            "category": "agendamento",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "est_02",
            "text": "Qual o valor do corte de cabelo?",
            "category": "precos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "est_03",
            "text": "Tem vaga hoje?",
            "category": "disponibilidade",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "otica": [
        {
            "id": "otica_01",
            "text": "Aceita o meu convenio?",
            "category": "convenio",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "otica_02",
            "text": "Qual o prazo para as lentes ficarem prontas?",
            "category": "prazos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "otica_03",
            "text": "Fazem exame de vista?",
            "category": "servicos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "educacao": [
        {
            "id": "edu_01",
            "text": "Como faco a matricula?",
            "category": "matricula",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "edu_02",
            "text": "Tem vaga para o ensino fundamental?",
            "category": "vagas",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "edu_03",
            "text": "Qual o valor da mensalidade?",
            "category": "precos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "ecommerce": [
        {
            "id": "eco_01",
            "text": "Tem produto disponivel?",
            "category": "estoque",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "eco_02",
            "text": "Qual o prazo de entrega?",
            "category": "entrega",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "eco_03",
            "text": "Como faco troca?",
            "category": "politicas",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
    "servicos": [
        {
            "id": "serv_01",
            "text": "Como voces funcionam?",
            "category": "servicos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "serv_02",
            "text": "Qual o investimento minimo?",
            "category": "precos",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
        {
            "id": "serv_03",
            "text": "Posso agendar uma conversa?",
            "category": "agendamento",
            "expected_behavior": "resposta_nao_vazia",
            "escalation_test": False,
        },
    ],
}

# Alias de normalizacao (mesmos do vertical_templates)
_ALIASES: dict[str, str] = {
    "confeitaria": "confeitaria",
    "gastronomia": "gastronomia",
    "restaurante": "gastronomia",
    "padaria": "gastronomia",
    "saude": "saude",
    "saúde": "saude",
    "clinica": "saude",
    "clínica": "saude",
    "estetica": "estetica",
    "estética": "estetica",
    "beleza": "estetica",
    "salao": "estetica",
    "salão": "estetica",
    "barbearia": "estetica",
    "otica": "otica",
    "ótica": "otica",
    "educacao": "educacao",
    "educação": "educacao",
    "escola": "educacao",
    "curso": "educacao",
    "ecommerce": "ecommerce",
    "e-commerce": "ecommerce",
    "loja": "ecommerce",
    "consorcio": "servicos",
    "consórcio": "servicos",
    "seguros": "servicos",
    "imobiliaria": "servicos",
    "contabilidade": "servicos",
    "advocacia": "servicos",
    "generico": "generico",
    "geral": "generico",
}


def get_test_questions(business_type: Optional[str]) -> list[dict]:
    """
    Retorna lista de 10 perguntas de teste para a vertical informada.

    Estrutura:
    - 7 perguntas genericas (sempre)
    - 3 perguntas especificas da vertical (fallback: apenas as 7 genericas)

    AC-5.2: se business_type nao tem template especifico, usa apenas as 7 genericas.
    """
    if not business_type:
        return GENERIC_QUESTIONS.copy()

    normalized = _ALIASES.get(business_type.lower().strip(), "")
    vertical_qs = VERTICAL_QUESTIONS.get(normalized, [])

    if not vertical_qs:
        # AC-5.2: fallback graceful — apenas genericas
        print(
            f"[test_questions] Vertical '{business_type}' sem template especifico — "
            "usando apenas perguntas genericas."
        )
        return GENERIC_QUESTIONS.copy()

    return GENERIC_QUESTIONS + vertical_qs[:3]
