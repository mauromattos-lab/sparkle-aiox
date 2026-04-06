"""
LIFECYCLE-2.1 — Pre-approved upsell approach scripts.

Each script has: opening, value_prop, cta, objection_handlers.
Variables: {client_name}, {business_name}, {months_active}, {health_score}, {volume}.
"""

SCRIPTS = {
    "upgrade_tier": {
        "opening": "Oi {client_name}! Vi que a {business_name} está voando — {volume} atendimentos no último mês! 🚀",
        "value_prop": "Com o plano Premium, você desbloqueia relatórios avançados, automações extras e prioridade no suporte. Clientes como você costumam dobrar o aproveitamento.",
        "cta": "Quer que eu te mostre o que muda na prática? Posso preparar uma comparação personalizada.",
        "objection_handlers": {
            "preco": "Entendo! O upgrade é um investimento, mas considerando que você já atende {volume}/mês, o custo por atendimento cai bastante.",
            "nao_preciso": "Sem problema! Fico feliz que o plano atual esteja funcionando bem. Se mudar de ideia, estou aqui.",
        },
    },
    "cross_sell_traffic": {
        "opening": "Oi {client_name}! A Zenya da {business_name} está mandando muito bem — Health Score {health_score}! 💪",
        "value_prop": "Notei que vocês ainda não usam tráfego pago. No nicho de vocês, empresas similares que combinam Zenya + Meta Ads aumentam o volume de leads em 3-5x.",
        "cta": "Posso montar uma projeção de ROI específica pro seu nicho? Sem compromisso.",
        "objection_handlers": {
            "preco": "Começamos com investimentos a partir de R$750/mês em ads + gestão. O retorno costuma aparecer no primeiro mês.",
            "ja_tentei": "Entendo a frustração. A diferença é que integramos a captação direto com a Zenya — o lead é atendido na hora, sem perder ninguém.",
        },
    },
    "cross_sell_zenya": {
        "opening": "Oi {client_name}! Vi que a {business_name} já usa nosso tráfego pago e os resultados estão bons!",
        "value_prop": "Só que muitos leads chegam fora do horário comercial e se perdem. Com a Zenya, seu atendimento funciona 24/7 — cada lead que o tráfego traz é atendido na hora.",
        "cta": "Quer ver uma demo de como ficaria para o seu negócio? Leva 5 minutos.",
        "objection_handlers": {
            "chatbot_ruim": "A Zenya é diferente de chatbot genérico — ela aprende o DNA do seu negócio, fala com a sua voz e resolve de verdade.",
            "preco": "O plano começa em R$500/mês. Considerando o que vocês já investem em tráfego, é o complemento que converte investimento em resultado.",
        },
    },
    "referral": {
        "opening": "Oi {client_name}! Muito obrigado pela parceria — {months_active} meses juntos! 🙌",
        "value_prop": "Você conhece algum empresário que poderia se beneficiar da Zenya? Temos um programa de indicação.",
        "cta": "Se indicar um amigo, ambos ganham 10% de desconto no próximo mês. Manda o contato e a gente cuida do resto!",
        "objection_handlers": {},
    },
}


def get_script(opportunity_type: str, context: dict = None) -> dict:
    """
    Return personalized script with context variables filled in.
    
    context keys: client_name, business_name, months_active, health_score, volume
    """
    template = SCRIPTS.get(opportunity_type)
    if not template:
        return {"error": f"Unknown opportunity type: {opportunity_type}"}

    ctx = context or {}
    result = {}
    for key, value in template.items():
        if isinstance(value, str):
            try:
                result[key] = value.format(**ctx)
            except KeyError:
                result[key] = value  # leave unformatted if context missing
        elif isinstance(value, dict):
            result[key] = {}
            for k, v in value.items():
                try:
                    result[key][k] = v.format(**ctx)
                except KeyError:
                    result[key][k] = v
        else:
            result[key] = value

    return result


def list_script_types() -> list[str]:
    return list(SCRIPTS.keys())
