"""
Iniciativa 1: Alerta de Risco — cliente sem atualização em agent_work_items há 48h+.

Query: clientes com status='ativo' em clients que não têm agent_work_items
atualizado nas últimas 48h, OU que têm pagamento vencido há > 3 dias.

Cron: diário às 9h30 Brasília (apscheduler).
Anti-spam: window_key diário por cliente — 1 alerta/cliente/dia máximo.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from runtime.db import supabase
from runtime.config import settings
from runtime.integrations.zapi import send_text as send_whatsapp_text


INITIATIVE_TYPE = "risk_alert"


async def handle_friday_initiative_risk(task: dict) -> dict:
    """Detecta clientes em risco e envia alerta via WhatsApp para Mauro."""
    results = {"sent": 0, "skipped_spam": 0, "errors": 0}

    # Query 1: clientes com pagamento vencido (via v_payments_overdue)
    try:
        overdue = await asyncio.to_thread(
            lambda: supabase.table("v_payments_overdue").select("*").execute()
        )
        at_risk_clients = overdue.data or []
    except Exception as e:
        print(f"[friday_risk] falha ao buscar v_payments_overdue: {e}")
        at_risk_clients = []

    # Query 2: clientes ativos sem update em agent_work_items há 48h+
    try:
        stale = await asyncio.to_thread(
            lambda: supabase.rpc("get_clients_without_recent_activity", {
                "hours_threshold": 48
            }).execute()
        )
        # Merge sem duplicar clientes já em at_risk_clients
        existing_ids = {c.get("client_id") for c in at_risk_clients}
        for row in (stale.data or []):
            if row.get("client_id") not in existing_ids:
                at_risk_clients.append(row)
    except Exception as e:
        print(f"[friday_risk] falha ao buscar clientes sem atividade: {e}")

    today_str = date.today().isoformat()

    for client in at_risk_clients:
        client_id = client.get("client_id") or client.get("id")
        client_name = client.get("cliente") or client.get("name") or "Cliente"
        # Fallback: usar whatsapp como chave proxy quando view nao tem client_id (ex: v_payments_overdue)
        client_key = str(client_id) if client_id else (client.get("whatsapp") or client_name).replace("+", "").replace(" ", "")
        window_key = f"{today_str}_{INITIATIVE_TYPE}_{client_key}"

        # Verificar anti-spam
        already_sent = await _check_already_sent(window_key)
        if already_sent:
            results["skipped_spam"] += 1
            continue

        # Montar mensagem
        days_overdue = client.get("dias_ate_vencimento")
        amount = client.get("valor") or client.get("mrr")

        if days_overdue is not None and days_overdue < 0:
            days_str = abs(int(days_overdue))
            msg = (
                f"\u26a0\ufe0f *Alerta de Risco \u2014 {client_name}*\n\n"
                f"Pagamento vencido h\u00e1 {days_str} dia(s). "
                f"Valor: R${float(amount):.2f}.\n\n"
                f"Quer que eu registre um follow-up ou voc\u00ea entra em contato agora?"
            )
        else:
            msg = (
                f"\u26a0\ufe0f *Alerta de Risco \u2014 {client_name}*\n\n"
                f"Sem atividade registrada nas \u00faltimas 48h. "
                f"Pode ser momento de verificar o status do cliente.\n\n"
                f"Quer registrar um check-in ou prefere que eu monitore mais um dia?"
            )

        # Enviar via Z-API para Mauro
        try:
            zapi_resp = await asyncio.to_thread(send_whatsapp_text, settings.mauro_whatsapp, msg)
            await _log_initiative(window_key, INITIATIVE_TYPE, client_id, client_name, msg, zapi_resp)
            results["sent"] += 1
        except Exception as e:
            print(f"[friday_risk] falha ao enviar alerta para {client_name}: {e}")
            results["errors"] += 1

    return {"message": f"Risk alert conclu\u00eddo: {results}"}


async def _check_already_sent(window_key: str) -> bool:
    try:
        r = await asyncio.to_thread(
            lambda: supabase.table("friday_initiative_log")
            .select("id")
            .eq("window_key", window_key)
            .maybe_single()
            .execute()
        )
        return bool(r.data)
    except Exception:
        return False  # em caso de erro, nao bloqueia o envio


async def _log_initiative(window_key, initiative_type, client_id, client_name, msg, zapi_resp):
    try:
        await asyncio.to_thread(
            lambda: supabase.table("friday_initiative_log").insert({
                "initiative_type": initiative_type,
                "client_id": str(client_id) if client_id else None,
                "client_name": client_name,
                "window_key": window_key,
                "message_preview": msg[:200],
                "zapi_response": zapi_resp if isinstance(zapi_resp, dict) else {"raw": str(zapi_resp)},
            }).execute()
        )
    except Exception as e:
        print(f"[friday_initiative] falha ao logar initiative {window_key}: {e}")
