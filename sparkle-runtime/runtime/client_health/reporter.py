"""
Weekly Report Generator — LIFECYCLE-1.3

Gera e envia relatório semanal de cada cliente ativo para o Mauro via WhatsApp.

Cron: toda segunda às 9h10 BRT (10 min após health_score_weekly às 8h10).

Fluxo:
  1. Busca todos clientes ativos em zenya_clients
  2. Para cada cliente, obtém último health score de client_health
  3. Obtém volume de mensagens dos últimos 7 dias de zenya_events
  4. Monta mensagem WhatsApp formatada (máx 500 chars)
  5. Envia para o número do Mauro via Z-API

Funções públicas:
  async generate_and_send_reports() -> dict
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase
from runtime.config import settings
from runtime.integrations import zapi

logger = logging.getLogger(__name__)

# ── Highlight e Recommendation ────────────────────────────


def _generate_highlight(score: int, classification: str, volume: int) -> str:
    """Gera destaque baseado no score e volume."""
    if classification == "healthy":
        if volume > 50:
            return "Semana excelente! Alto volume de atendimento."
        return "Cliente saudavel e estavel."
    elif classification == "attention":
        if volume == 0:
            return "Sem mensagens esta semana — monitorar."
        return "Score em zona de atencao, mas ativo."
    elif classification == "risk":
        return "Score em risco — avaliar intervencao."
    else:  # critical
        return "Score critico — acao necessaria."


def _generate_recommendation(classification: str, volume: int, days_since_last: int | None) -> str:
    """Gera recomendacao baseada na classificacao."""
    if classification == "healthy":
        return "Manter acompanhamento regular."
    elif classification == "attention":
        if days_since_last and days_since_last > 7:
            return "Contatar cliente para check-in."
        return "Verificar pagamento e engajamento."
    elif classification == "risk":
        return "Ligar ou enviar mensagem de suporte."
    else:  # critical
        return "Contato urgente — risco de churn."


def _format_payment_status(payment_signal: dict) -> str:
    """Converte status de pagamento para texto legivel."""
    status_map = {
        "ACTIVE": "Em dia",
        "OVERDUE": "Em atraso",
        "LATE": "Em atraso",
        "INACTIVE": "Inativo",
        "CANCELLED": "Cancelado",
        "DELETED": "Cancelado",
        "no_subscription": "Sem assinatura",
        "error": "Nao verificado",
    }
    raw_status = (payment_signal.get("status") or "").upper()
    return status_map.get(raw_status, raw_status or "Desconhecido")


def _format_score_emoji(classification: str) -> str:
    emoji_map = {
        "healthy": "verde",
        "attention": "amarelo",
        "risk": "laranja",
        "critical": "vermelho",
    }
    return emoji_map.get(classification, "cinza")


def _build_report_message(
    business_name: str,
    score: int,
    classification: str,
    volume: int,
    payment_status: str,
    days_since_last: int | None,
    highlight: str,
    recommendation: str,
) -> str:
    """Monta a mensagem de relatorio semanal (max 500 chars)."""
    days_text = f"{days_since_last} dias" if days_since_last is not None else "N/A"

    msg = (
        f"Relatorio Semanal — {business_name}\n\n"
        f"Health Score: {score}/100 ({classification})\n\n"
        f"Metricas da Semana:\n"
        f"- Mensagens processadas: {volume}\n"
        f"- Pagamento: {payment_status}\n"
        f"- Ultimo acesso: {days_text} atras\n\n"
        f"Destaque: {highlight}\n\n"
        f"Recomendacao: {recommendation}"
    )

    # Truncar se necessario para respeitar o limite de 500 chars
    if len(msg) > 500:
        msg = msg[:497] + "..."

    return msg


# ── Main entry point ─────────────────────────────────────


async def generate_and_send_reports() -> dict:
    """
    Gera e envia relatorio semanal de todos os clientes ativos para o Mauro.

    Returns:
        dict com total, sent, skipped, errors
    """
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        logger.error("[reporter] MAURO_WHATSAPP nao configurado — abortando")
        return {"total": 0, "sent": 0, "skipped": 0, "errors": 1}

    # Normaliza numero: remove + e espacos
    mauro_phone = mauro_phone.replace("+", "").replace(" ", "")

    # Busca todos os clientes ativos
    try:
        clients_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("id, business_name, active")
            .eq("active", True)
            .execute()
        )
    except Exception as e:
        logger.error("[reporter] falha ao buscar clientes: %s", e)
        return {"total": 0, "sent": 0, "skipped": 0, "errors": 1}

    clients = clients_res.data or []
    if not clients:
        logger.info("[reporter] nenhum cliente ativo encontrado")
        return {"total": 0, "sent": 0, "skipped": 0, "errors": 0}

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    total = len(clients)
    sent = 0
    skipped = 0
    errors = 0

    for client in clients:
        client_id = client["id"]
        business_name = client.get("business_name", "Cliente")

        try:
            # 1. Health score mais recente
            health_res = await asyncio.to_thread(
                lambda cid=client_id: supabase.table("client_health")
                .select("score, classification, signals, calculated_at")
                .eq("client_id", cid)
                .order("calculated_at", desc=True)
                .limit(1)
                .execute()
            )

            if not health_res.data:
                logger.info("[reporter] sem health score para %s — pulando", business_name)
                skipped += 1
                continue

            health = health_res.data[0]
            score = health.get("score", 0)
            classification = health.get("classification", "critical")
            signals = health.get("signals") or {}

            # 2. Volume ultimos 7 dias
            volume_res = await asyncio.to_thread(
                lambda cid=client_id: supabase.table("zenya_events")
                .select("id", count="exact")
                .eq("client_id", cid)
                .gte("created_at", seven_days_ago)
                .execute()
            )
            volume = volume_res.count or 0

            # 3. Extrair dados dos sinais
            payment_signal = signals.get("payment") or {}
            access_signal = signals.get("access") or {}
            days_since_last = access_signal.get("days_since_last")
            payment_status = _format_payment_status(payment_signal)

            # 4. Gerar highlight e recomendacao
            highlight = _generate_highlight(score, classification, volume)
            recommendation = _generate_recommendation(classification, volume, days_since_last)

            # 5. Montar mensagem
            message = _build_report_message(
                business_name=business_name,
                score=score,
                classification=classification,
                volume=volume,
                payment_status=payment_status,
                days_since_last=days_since_last,
                highlight=highlight,
                recommendation=recommendation,
            )

            # 6. Enviar para o Mauro
            await asyncio.to_thread(lambda m=message: zapi.send_text(mauro_phone, m))

            logger.info(
                "[reporter] relatorio enviado — client=%s score=%d classification=%s",
                business_name, score, classification,
            )
            sent += 1

        except Exception as e:
            logger.error("[reporter] erro ao processar cliente %s: %s", business_name, e)
            errors += 1

    logger.info(
        "[reporter] concluido — total=%d sent=%d skipped=%d errors=%d",
        total, sent, skipped, errors,
    )
    return {"total": total, "sent": sent, "skipped": skipped, "errors": errors}
