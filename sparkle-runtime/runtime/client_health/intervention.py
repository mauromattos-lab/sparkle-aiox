"""
Inactivity Detection & Reactivation — LIFECYCLE-1.3

Detecta clientes inativos e dispara intervencao automatica.

Cron: todo dia as 10h BRT.

Logica:
  - Inativo 21-27 dias: envia mensagem de reativacao para o WhatsApp DO CLIENTE
  - Inativo 28+ dias: cria task friday_alert para Friday escalar com Mauro
  - Nao reenvia no mesmo dia (dedup via check de task criada hoje)

Funcoes publicas:
  async check_and_intervene() -> dict
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase
from runtime.config import settings
from runtime.integrations import zapi

logger = logging.getLogger(__name__)


# ── Dedup check ───────────────────────────────────────────


async def _already_intervened_today(client_id: str) -> bool:
    """
    Verifica se ja foi criada uma task de intervencao para este cliente hoje.
    Evita duplicar alertas no mesmo dia.
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id")
            .eq("client_id", client_id)
            .in_("task_type", ["client_reactivation", "friday_alert"])
            .gte("created_at", today_start)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        logger.warning("[intervention] dedup check falhou para %s: %s", client_id, e)
        return False


# ── Intervencao: reativacao direta ao cliente ─────────────


async def _send_reactivation_message(client_id: str, business_name: str, phone_number: str) -> bool:
    """
    Envia mensagem de reativacao para o WhatsApp do cliente.
    Normaliza o numero de telefone antes do envio.
    """
    if not phone_number:
        logger.info("[intervention] cliente %s sem telefone cadastrado — pulando", business_name)
        return False

    # Normaliza numero: remove +, espacos, tracos, parenteses
    phone = phone_number.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Extrai nome amigavel da Zenya (usa business_name como fallback)
    zenya_name = business_name

    message = (
        f"Oi! Aqui e da Sparkle.\n\n"
        f"Notamos que a {zenya_name} nao recebeu mensagens recentemente. "
        f"Precisa de algum ajuste? Estamos aqui pra ajudar!\n\n"
        f"Responda ajuda e nosso time entra em contato."
    )

    try:
        await asyncio.to_thread(lambda: zapi.send_text(phone, message))
        logger.info("[intervention] mensagem de reativacao enviada para %s (%s)", business_name, phone)
        return True
    except Exception as e:
        logger.error("[intervention] falha ao enviar reativacao para %s: %s", business_name, e)
        return False


# ── Intervencao: escalate para Friday ────────────────────


async def _escalate_to_friday(client_id: str, business_name: str, inactive_weeks: int) -> bool:
    """
    Cria task friday_alert no Supabase para Friday escalar com Mauro.
    """
    try:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "friday_alert",
                "payload": {
                    "alert": "client_inactive",
                    "client_id": client_id,
                    "client_name": business_name,
                    "inactive_weeks": inactive_weeks,
                    "message": f"Cliente {business_name} esta inativo ha {inactive_weeks} semanas.",
                },
                "status": "pending",
                "priority": 8,
            }).execute()
        )
        logger.info(
            "[intervention] friday_alert criado para %s (%d semanas inativo)",
            business_name, inactive_weeks,
        )
        return True
    except Exception as e:
        logger.error("[intervention] falha ao criar friday_alert para %s: %s", business_name, e)
        return False


# ── Main entry point ─────────────────────────────────────


async def check_and_intervene() -> dict:
    """
    Verifica clientes inativos e aplica intervencao conforme limiar de dias.

    Regras:
      21-27 dias sem mensagem -> envia reativacao para WhatsApp do cliente
      28+ dias sem mensagem  -> cria friday_alert para escalar com Mauro

    Returns:
        dict com total_checked, reactivated, escalated, skipped, errors
    """
    now = datetime.now(timezone.utc)
    twenty_one_days_ago = (now - timedelta(days=21)).isoformat()

    # Busca todos os clientes ativos
    try:
        clients_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("id, business_name, phone_number, active")
            .eq("active", True)
            .execute()
        )
    except Exception as e:
        logger.error("[intervention] falha ao buscar clientes: %s", e)
        return {"total_checked": 0, "reactivated": 0, "escalated": 0, "skipped": 0, "errors": 1}

    clients = clients_res.data or []
    if not clients:
        logger.info("[intervention] nenhum cliente ativo encontrado")
        return {"total_checked": 0, "reactivated": 0, "escalated": 0, "skipped": 0, "errors": 0}

    total_checked = len(clients)
    reactivated = 0
    escalated = 0
    skipped = 0
    errors = 0

    for client in clients:
        client_id = client["id"]
        business_name = client.get("business_name", "Cliente")
        phone_number = client.get("phone_number", "") or ""

        try:
            # Verifica o ultimo evento do cliente (qualquer mensagem)
            last_event_res = await asyncio.to_thread(
                lambda cid=client_id: supabase.table("zenya_events")
                .select("created_at")
                .eq("client_id", cid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            last_event_data = last_event_res.data or []

            # Determinar dias de inatividade
            if not last_event_data:
                # Nunca teve evento — considera inativo desde a criacao do cliente
                # Busca created_at do cliente para calcular
                client_created_res = await asyncio.to_thread(
                    lambda cid=client_id: supabase.table("zenya_clients")
                    .select("created_at")
                    .eq("id", cid)
                    .maybe_single()
                    .execute()
                )
                client_data = client_created_res.data if client_created_res and hasattr(client_created_res, "data") else client_created_res
                if client_data and client_data.get("created_at"):
                    created_at_str = client_data["created_at"]
                    created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    days_inactive = (now - created_dt).days
                else:
                    # Sem dados suficientes — pular
                    skipped += 1
                    continue
            else:
                last_event_at_str = last_event_data[0]["created_at"]
                last_event_dt = datetime.fromisoformat(last_event_at_str.replace("Z", "+00:00"))
                days_inactive = (now - last_event_dt).days

            # Aplica limiar de intervencao
            if days_inactive < 21:
                # Cliente ativo — sem intervencao
                skipped += 1
                continue

            # Verifica se ja interveio hoje
            already_done = await _already_intervened_today(client_id)
            if already_done:
                logger.info("[intervention] ja interveio hoje para %s — pulando", business_name)
                skipped += 1
                continue

            inactive_weeks = days_inactive // 7

            if 21 <= days_inactive <= 27:
                # Intervencao leve: mensagem direta ao cliente
                success = await _send_reactivation_message(client_id, business_name, phone_number)
                if success:
                    # Registra a intervencao como task para dedup futuro
                    await asyncio.to_thread(
                        lambda: supabase.table("runtime_tasks").insert({
                            "agent_id": "friday",
                            "client_id": client_id,
                            "task_type": "client_reactivation",
                            "payload": {
                                "client_id": client_id,
                                "client_name": business_name,
                                "days_inactive": days_inactive,
                                "triggered_by": "intervention_check",
                            },
                            "status": "completed",
                            "priority": 6,
                        }).execute()
                    )
                    reactivated += 1
                else:
                    errors += 1
            else:
                # 28+ dias: escalate para Friday
                success = await _escalate_to_friday(client_id, business_name, inactive_weeks)
                if success:
                    escalated += 1
                else:
                    errors += 1

        except Exception as e:
            logger.error("[intervention] erro ao processar cliente %s: %s", business_name, e)
            errors += 1

    logger.info(
        "[intervention] concluido — total=%d reactivated=%d escalated=%d skipped=%d errors=%d",
        total_checked, reactivated, escalated, skipped, errors,
    )
    return {
        "total_checked": total_checked,
        "reactivated": reactivated,
        "escalated": escalated,
        "skipped": skipped,
        "errors": errors,
    }
