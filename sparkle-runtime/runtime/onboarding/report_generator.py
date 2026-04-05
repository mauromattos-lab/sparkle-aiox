"""
ONB-1.9: Gerador de relatorio semanal pos-go-live.

Formata relatorio de 1a semana como mensagem WhatsApp legivel para Mauro via Friday.
"""
from __future__ import annotations

from datetime import datetime, timezone


def generate_weekly_report(client_name: str, metrics: dict, health: dict) -> str:
    """
    AC-4.1 / AC-4.2: Gera relatorio da 1a semana formatado como mensagem WhatsApp.

    Args:
        client_name: Nome do cliente
        metrics: resultado de collect_health_metrics()
        health: resultado de evaluate_health()

    Returns:
        Mensagem formatada em texto para envio via Friday
    """
    volume_7d = metrics.get("volume_7d", 0)
    volume_48h = metrics.get("volume_48h", 0)
    escalation_pct = metrics.get("escalation_pct")
    sentiment = metrics.get("sentiment", {})
    status = health.get("status", "unknown")
    alerts = health.get("alerts", [])
    data_source = metrics.get("data_source", "unavailable")

    # Media por dia (7 dias)
    avg_per_day = round(volume_7d / 7, 1) if volume_7d else 0

    # Sentiment percentuais
    total_sentiment = max(sentiment.get("total", 0), 1)
    pos_pct = round((sentiment.get("positivo", 0) / total_sentiment) * 100)
    neu_pct = round((sentiment.get("neutro", 0) / total_sentiment) * 100)
    neg_pct = round((sentiment.get("negativo", 0) / total_sentiment) * 100)

    # Escalacao
    if escalation_pct is not None:
        escalation_str = f"{escalation_pct:.0f}% das conversas"
    else:
        escalation_str = "Dados indisponiveis"

    # Status legivel
    status_map = {
        "healthy": "SAUDAVEL",
        "warning": "ATENCAO",
        "critical": "CRITICO",
        "unknown": "INDETERMINADO",
    }
    status_label = status_map.get(status, status.upper())

    # Incidentes
    incidentes_count = len(alerts)
    if incidentes_count == 0:
        incidentes_str = "Nenhum alerta na semana"
    elif incidentes_count == 1:
        incidentes_str = f"1 alerta na semana"
    else:
        incidentes_str = f"{incidentes_count} alertas na semana"

    # Fonte de dados
    fonte_nota = ""
    if data_source == "brain_raw_ingestions":
        fonte_nota = "\n_Nota: dados baseados em registros de ingestao (zenya_conversations indisponivel)_"
    elif data_source == "unavailable":
        fonte_nota = "\n_Nota: dados de conversas indisponiveis — verificar configuracao_"

    report = (
        f"Relatorio 1a Semana — {client_name}\n"
        f"\n"
        f"Total de conversas: {volume_7d}\n"
        f"Media por dia: {avg_per_day}\n"
        f"Ultimas 48h: {volume_48h} conversas\n"
        f"Escalacao: {escalation_str}\n"
        f"Sentiment: {pos_pct}% positivo | {neu_pct}% neutro | {neg_pct}% negativo\n"
        f"Incidentes: {incidentes_str}\n"
        f"Status geral: {status_label}"
        f"{fonte_nota}\n"
        f"\n"
        f"— Friday, monitorando sua Zenya"
    )

    return report


def format_alert_message(client_name: str, alert: dict) -> str:
    """
    Formata mensagem de alerta para Friday com contexto do cliente.
    """
    alert_type = alert.get("type", "unknown")
    message = alert.get("message", "Alerta sem descricao.")
    severity = alert.get("severity", "warning").upper()

    prefix = "ATENCAO" if severity == "WARNING" else "CRITICO"

    return f"{prefix}: {client_name} — {message}"
