"""
Onboarding — ONB-3: Templates de persona e FAQ por vertical para Zenya.

Fornece:
- PERSONA_TEMPLATES: template base de soul_prompt por vertical
- FAQ_TEMPLATES: perguntas e respostas base por vertical
- get_persona_template(business_type): retorna template da vertical
- get_faq_template(business_type): retorna FAQ base da vertical
"""
from __future__ import annotations

from typing import Optional


# ── Aliases de normalização ────────────────────────────────────

_ALIASES: dict[str, str] = {
    "confeitaria": "confeitaria",
    "gastronomia": "gastronomia",
    "restaurante": "gastronomia",
    "padaria": "gastronomia",
    "lanchonete": "gastronomia",
    "saude": "saude",
    "saúde": "saude",
    "clinica": "saude",
    "clínica": "saude",
    "medico": "saude",
    "médico": "saude",
    "fisioterapia": "saude",
    "odontologia": "saude",
    "farmacia": "saude",
    "farmácia": "saude",
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
    "cursinho": "educacao",
    "ecommerce": "ecommerce",
    "e-commerce": "ecommerce",
    "loja": "ecommerce",
    "loja virtual": "ecommerce",
    "consorcio": "servicos",
    "consórcio": "servicos",
    "seguros": "servicos",
    "imobiliaria": "servicos",
    "imobiliária": "servicos",
    "contabilidade": "servicos",
    "advocacia": "servicos",
    "generico": "generico",
    "geral": "generico",
}


# ── Templates de Persona por vertical ─────────────────────────
# Usado como guia para o LLM ao gerar o soul_prompt.
# Variáveis: {business_name}, {vertical_context}

PERSONA_TEMPLATES: dict[str, str] = {
    "confeitaria": """
VERTICAL: Confeitaria / Doceria
FOCO: Pedidos, encomendas, cardápio, prazos, entregas, preços
TOM: Caloroso, acolhedor, levemente informal, usa emojis com moderação
ESCALAÇÃO PRIORITÁRIA: Pedidos acima de R$300, casamentos/eventos, reclamações de qualidade
REGRAS CRÍTICAS: Prazo mínimo de encomenda, restrições alérgenos, política de cancelamento
PERGUNTAS TÍPICAS: Cardápio do dia, tem X disponível?, faz entrega?, prazo encomenda
""".strip(),

    "gastronomia": """
VERTICAL: Gastronomia / Restaurante / Delivery
FOCO: Cardápio, pedidos, delivery, horários, reservas
TOM: Animado, acolhedor, informal mas profissional
ESCALAÇÃO PRIORITÁRIA: Reservas para grupos grandes, reclamações, pedidos especiais
REGRAS CRÍTICAS: Área de entrega, taxa mínima, horário de fechamento de pedidos
PERGUNTAS TÍPICAS: O que tem hoje?, faz delivery?, tempo de espera?, aceita cartão?
""".strip(),

    "saude": """
VERTICAL: Saúde / Clínica / Consultório
FOCO: Agendamentos, convênios, serviços disponíveis, localização
TOM: Profissional, empático, tranquilizador, formal
ESCALAÇÃO PRIORITÁRIA: Urgências médicas, reclamações, casos complexos — SEMPRE para humano
REGRAS CRÍTICAS: Nunca dar conselhos médicos. Para emergências, orientar para SAMU/UPA.
PERGUNTAS TÍPICAS: Aceita [plano]?, como agendar?, qual o valor da consulta?, tem vaga hoje?
""".strip(),

    "estetica": """
VERTICAL: Estética / Beleza / Salão / Barbearia
FOCO: Agendamentos, serviços disponíveis, preços, profissionais
TOM: Descontraído, amigável, levemente fashion, informal
ESCALAÇÃO PRIORITÁRIA: Reclamações de serviço, pedidos de reembolso
REGRAS CRÍTICAS: Política de cancelamento com antecedência mínima, lista de espera
PERGUNTAS TÍPICAS: Tem horário hoje?, quanto custa X?, tem [profissional] disponível?
""".strip(),

    "otica": """
VERTICAL: Ótica
FOCO: Produtos, exames, convênios, prazos de lentes, preços
TOM: Profissional e acolhedor, moderadamente formal
ESCALAÇÃO PRIORITÁRIA: Reclamações, garantias, óculos com defeito — para humano
REGRAS CRÍTICAS: Não consultar laudos ou receitas. Exames presenciais obrigatórios.
PERGUNTAS TÍPICAS: Aceita [plano]?, quanto tempo para ficar pronto?, tem armação X?
""".strip(),

    "educacao": """
VERTICAL: Educação / Escola / Curso
FOCO: Matrículas, turmas, horários, valores, material
TOM: Acolhedor, prestativo, profissional, confiável
ESCALAÇÃO PRIORITÁRIA: Reclamações pedagógicas, situações financeiras complexas
REGRAS CRÍTICAS: Não compartilhar dados de alunos. Dúvidas pedagógicas para coordenação.
PERGUNTAS TÍPICAS: Como é a matrícula?, quais turmas têm vaga?, quando começa?, qual o valor?
""".strip(),

    "ecommerce": """
VERTICAL: E-commerce / Loja Virtual
FOCO: Pedidos, status, trocas, prazo de entrega, pagamento
TOM: Ágil, objetivo, prestativo, profissional
ESCALAÇÃO PRIORITÁRIA: Reclamações, produtos com defeito, pedidos não entregues
REGRAS CRÍTICAS: Política de troca/devolução, prazos do Código do Consumidor
PERGUNTAS TÍPICAS: Meu pedido está onde?, posso trocar?, quando chega?, frete grátis?
""".strip(),

    "servicos": """
VERTICAL: Serviços Profissionais (Consórcio, Seguros, Imobiliária, Contabilidade, etc.)
FOCO: Consultas iniciais, agendamentos, informações gerais, lead qualification
TOM: Profissional, confiável, objetivo, sem jargões excessivos
ESCALAÇÃO PRIORITÁRIA: Propostas, negociações, questões técnicas — sempre para especialista
REGRAS CRÍTICAS: Não fazer promessas sobre resultados. Dados específicos para humano.
PERGUNTAS TÍPICAS: Como funciona?, qual o investimento mínimo?, posso agendar uma conversa?
""".strip(),

    "generico": """
VERTICAL: Negócio Geral
FOCO: Atendimento inicial, informações sobre produtos/serviços, agendamentos
TOM: Amigável, prestativo, profissional
ESCALAÇÃO PRIORITÁRIA: Reclamações, dúvidas complexas, negociações
REGRAS CRÍTICAS: Dentro do horário de atendimento, sempre responder prontamente
PERGUNTAS TÍPICAS: Quanto custa?, como funciona?, vocês atendem [localidade]?
""".strip(),
}


# ── Templates de FAQ por vertical ─────────────────────────────
# Lista de pares (pergunta, resposta_base) para seed da KB.
# Respostas são marcadas com [PREENCHER] onde dados específicos são necessários.

FAQ_TEMPLATES: dict[str, list[dict]] = {
    "confeitaria": [
        {"q": "Qual o horário de funcionamento?", "a": "[PREENCHER: horário de funcionamento da confeitaria]"},
        {"q": "Fazem entrega?", "a": "[PREENCHER: se faz entrega, área de cobertura e taxa]"},
        {"q": "Qual o prazo mínimo para encomendas?", "a": "[PREENCHER: prazo mínimo de encomenda]"},
        {"q": "Como faço um pedido?", "a": "Você pode fazer seu pedido diretamente por aqui no WhatsApp. Me diga o que deseja e a data de entrega!"},
        {"q": "Quais formas de pagamento aceitam?", "a": "[PREENCHER: formas de pagamento aceitas]"},
        {"q": "Fazem bolo personalizado?", "a": "[PREENCHER: se faz personalizado, opções e preços]"},
        {"q": "Tem cardápio disponível?", "a": "[PREENCHER: link ou descrição do cardápio]"},
        {"q": "Trabalham com casamentos/eventos?", "a": "[PREENCHER: se atende eventos, como funciona]"},
        {"q": "Posso cancelar ou alterar meu pedido?", "a": "[PREENCHER: política de cancelamento]"},
        {"q": "Tem opção sem glúten ou vegana?", "a": "[PREENCHER: opções especiais disponíveis]"},
    ],

    "gastronomia": [
        {"q": "Qual o horário de funcionamento?", "a": "[PREENCHER: horário de funcionamento]"},
        {"q": "Fazem delivery?", "a": "[PREENCHER: se faz delivery, apps disponíveis, área de cobertura]"},
        {"q": "Têm mesa disponível para hoje?", "a": "Para reservas, me diga o horário desejado e quantidade de pessoas que verifico pra você!"},
        {"q": "Qual o tempo médio de espera para delivery?", "a": "[PREENCHER: tempo médio de entrega]"},
        {"q": "Têm cardápio online?", "a": "[PREENCHER: link do cardápio ou descrição]"},
        {"q": "Aceitam cartão?", "a": "[PREENCHER: formas de pagamento]"},
        {"q": "Têm opções vegetarianas?", "a": "[PREENCHER: opções para dietas especiais]"},
        {"q": "Têm estacionamento?", "a": "[PREENCHER: informações sobre estacionamento]"},
        {"q": "Como faço uma reserva?", "a": "Posso anotar a reserva por aqui mesmo! Me diga: data, horário e número de pessoas."},
    ],

    "saude": [
        {"q": "Qual o horário de atendimento?", "a": "[PREENCHER: horário de atendimento]"},
        {"q": "Como faço para agendar uma consulta?", "a": "Para agendar, me informe sua disponibilidade de dia e horário que verifico as vagas para você!"},
        {"q": "Aceitam o plano [X]?", "a": "[PREENCHER: lista de convênios aceitos]"},
        {"q": "Qual o valor da consulta particular?", "a": "[PREENCHER: valores de consulta]"},
        {"q": "Precisam de encaminhamento?", "a": "[PREENCHER: se exige encaminhamento ou aceita direto]"},
        {"q": "Atendem emergências?", "a": "Para emergências médicas, ligue para o SAMU (192) ou dirija-se à UPA mais próxima. Para agendamentos urgentes, me avise e verifico disponibilidade."},
        {"q": "Onde fica a clínica?", "a": "[PREENCHER: endereço completo]"},
        {"q": "Posso cancelar uma consulta?", "a": "[PREENCHER: política de cancelamento]"},
        {"q": "Vocês são especializados em quê?", "a": "[PREENCHER: especialidades disponíveis]"},
        {"q": "Tem estacionamento?", "a": "[PREENCHER: informações de acesso]"},
    ],

    "estetica": [
        {"q": "Qual o horário de atendimento?", "a": "[PREENCHER: horário de atendimento]"},
        {"q": "Como faço para agendar?", "a": "Para agendar, me diga o serviço desejado e sua disponibilidade que procuro um horário perfeito pra você!"},
        {"q": "Qual o valor do serviço X?", "a": "[PREENCHER: tabela de preços]"},
        {"q": "Têm vaga para hoje?", "a": "Deixa eu verificar! Me diga qual serviço e horário prefere."},
        {"q": "Aceitam cartão?", "a": "[PREENCHER: formas de pagamento]"},
        {"q": "Como funciona o cancelamento?", "a": "[PREENCHER: política de cancelamento com prazo]"},
        {"q": "Tem lista de espera?", "a": "Sim! Me deixa na lista de espera para um horário. Se abrir uma vaga, eu te aviso."},
        {"q": "Atendem sem agendamento?", "a": "[PREENCHER: política de atendimento sem hora marcada]"},
    ],

    "otica": [
        {"q": "Qual o horário de atendimento?", "a": "[PREENCHER: horário de funcionamento]"},
        {"q": "Fazem exame de vista?", "a": "[PREENCHER: se faz exame, como agendar, valor]"},
        {"q": "Aceitam o plano X?", "a": "[PREENCHER: convênios aceitos]"},
        {"q": "Qual o prazo para as lentes ficarem prontas?", "a": "[PREENCHER: prazo de produção de lentes]"},
        {"q": "Têm óculos para grau alto?", "a": "[PREENCHER: capacidade de atendimento]"},
        {"q": "Como funciona a garantia?", "a": "[PREENCHER: política de garantia]"},
        {"q": "Aceitam receita de outro médico?", "a": "Sim, aceitamos receitas de qualquer oftalmologista."},
        {"q": "Têm armações infantis?", "a": "[PREENCHER: linha infantil disponível]"},
        {"q": "Onde ficam?", "a": "[PREENCHER: endereço e referência]"},
    ],

    "educacao": [
        {"q": "Como funciona a matrícula?", "a": "[PREENCHER: processo de matrícula]"},
        {"q": "Quais turmas têm vaga?", "a": "[PREENCHER: turmas disponíveis com vagas]"},
        {"q": "Qual o valor da mensalidade?", "a": "[PREENCHER: valores e condições]"},
        {"q": "Quando começa o próximo período?", "a": "[PREENCHER: calendário de início]"},
        {"q": "Atendem qual faixa etária?", "a": "[PREENCHER: público atendido]"},
        {"q": "Têm material incluso?", "a": "[PREENCHER: o que está incluso na mensalidade]"},
        {"q": "Têm transporte escolar?", "a": "[PREENCHER: se há transporte disponível]"},
        {"q": "Como funciona a comunicação com os pais?", "a": "[PREENCHER: canal principal de comunicação]"},
        {"q": "Têm desconto para irmãos?", "a": "[PREENCHER: política de descontos]"},
        {"q": "Aceitam bolsa/financiamento?", "a": "[PREENCHER: opções de financiamento disponíveis]"},
    ],

    "ecommerce": [
        {"q": "Como rastreio meu pedido?", "a": "[PREENCHER: como fazer rastreamento]"},
        {"q": "Qual o prazo de entrega?", "a": "[PREENCHER: prazos por região/modalidade]"},
        {"q": "Posso trocar ou devolver?", "a": "[PREENCHER: política de troca/devolução]"},
        {"q": "Quais formas de pagamento aceitam?", "a": "[PREENCHER: formas de pagamento]"},
        {"q": "Têm frete grátis?", "a": "[PREENCHER: condições para frete grátis]"},
        {"q": "O produto X está disponível?", "a": "Me diga qual produto você procura que verifico o estoque!"},
        {"q": "O produto chegou com defeito. O que faço?", "a": "Sinto muito pelo inconveniente! Me manda uma foto do produto e os dados do pedido que aciono nosso time de qualidade para resolver rapidinho."},
        {"q": "Posso cancelar meu pedido?", "a": "[PREENCHER: prazo e como cancelar]"},
        {"q": "Quanto tempo leva para o reembolso?", "a": "[PREENCHER: prazo de reembolso]"},
    ],

    "servicos": [
        {"q": "O que vocês fazem exatamente?", "a": "[PREENCHER: descrição clara dos serviços]"},
        {"q": "Qual o investimento para começar?", "a": "Os valores dependem do seu perfil e necessidades. Que tal marcarmos uma conversa rápida para eu te apresentar as opções?"},
        {"q": "Como funciona o processo?", "a": "[PREENCHER: passo a passo do serviço]"},
        {"q": "Qual o prazo para resultados?", "a": "[PREENCHER: expectativa de prazo realista]"},
        {"q": "Vocês são regulamentados?", "a": "[PREENCHER: registro/regulamentação do setor]"},
        {"q": "Posso falar com um especialista?", "a": "Claro! Me passe seus dados e o melhor horário para contato que um especialista entra em contato."},
        {"q": "Atendem em qual região?", "a": "[PREENCHER: área de atuação]"},
        {"q": "Têm contrato?", "a": "[PREENCHER: informações sobre contrato]"},
    ],

    "generico": [
        {"q": "Qual o horário de funcionamento?", "a": "[PREENCHER: horário de funcionamento]"},
        {"q": "Qual o valor do serviço/produto?", "a": "[PREENCHER: tabela de preços ou como solicitar orçamento]"},
        {"q": "Como funciona?", "a": "[PREENCHER: descrição do serviço/produto]"},
        {"q": "Vocês atendem na minha região?", "a": "[PREENCHER: área de atendimento]"},
        {"q": "Como faço para contratar/comprar?", "a": "[PREENCHER: processo de contratação/compra]"},
        {"q": "Quais formas de pagamento aceitam?", "a": "[PREENCHER: formas de pagamento]"},
        {"q": "Posso falar com um humano?", "a": "Claro! Vou chamar nossa equipe. Um momento."},
        {"q": "Vocês são confiáveis?", "a": "[PREENCHER: credenciais, tempo de mercado, diferenciais]"},
    ],
}

# FAQ universal (presente em todos os setores)
FAQ_UNIVERSAL: list[dict] = [
    {
        "q": "Vocês são atendidos por IA ou por humano?",
        "a": (
            "Sou a Zenya, uma assistente virtual inteligente! "
            "Consigo responder a maioria das dúvidas sobre nossos produtos e serviços. "
            "Para assuntos mais complexos, chamo nossa equipe humana."
        ),
    },
    {
        "q": "Quero falar com uma pessoa real",
        "a": (
            "Sem problema! Vou chamar nossa equipe agora. "
            "Um instante por favor."
        ),
    },
    {
        "q": "Você é um robô?",
        "a": (
            "Sou a Zenya, uma assistente virtual que usa inteligência artificial "
            "para te ajudar de forma rápida e precisa. "
            "Se preferir falar com um humano, é só me avisar!"
        ),
    },
]


# ── Funções públicas ───────────────────────────────────────────

def _normalize(business_type: Optional[str]) -> str:
    if not business_type:
        return "generico"
    key = business_type.lower().strip()
    return _ALIASES.get(key, "generico")


def get_persona_template(business_type: Optional[str]) -> str:
    """Retorna o template de persona para a vertical do business_type."""
    vertical = _normalize(business_type)
    return PERSONA_TEMPLATES.get(vertical, PERSONA_TEMPLATES["generico"])


def get_faq_template(business_type: Optional[str]) -> list[dict]:
    """
    Retorna FAQ base para a vertical + FAQ universal.
    Cada item é um dict com chaves 'q' e 'a'.
    """
    vertical = _normalize(business_type)
    vertical_faq = FAQ_TEMPLATES.get(vertical, FAQ_TEMPLATES["generico"])
    # Universal always at the end
    return vertical_faq + FAQ_UNIVERSAL
