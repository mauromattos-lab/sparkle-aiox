"""
Iniciativa 2: Briefing de Risco de Vencimento — cliente com pagamento em <= 3 dias sem contato.

Query: v_billing_calendar WHERE dias_ate_vencimento <= 3 AND dias_ate_vencimento >= 0
       E não há registro de follow-up recente em friday_initiative_log.

Cron: diário às 8h45 Brasília (antes do briefing das 9h).
Anti-spam: window_key diário por cliente.
"""
from __future__ import annotations

import asyncio
from datetime import date

from runtime.db import supabase
from runtime.config import settings
from runtime.integrations.zapi import send_text as send_whatsapp_text


INITIATIVE_TYPE = "billing_risk"


async def handle_friday_initiative_billing(task: dict) -> dict:
    results = {"sent": 0, "skipped_spam": 0, "errors": 0}
    today_str = date.today().isoformat()

    try:
        billing = await asyncio.to_thread(
            lambda: supabase.table("v_billing_calendar")
            .select("*")
            .lte("dias_ate_vencimento", 3)
            .gte("dias_ate_vencimento", 0)
            .execute()
        )
        upcoming = billing.data or []
    except Exception as e:
        print(f"[friday_billing] falha ao buscar v_billing_calendar: {e}")
        return {"message": f"Billing risk erro: {e}"}

    for entry in upcoming:
        client_name = entry.get("cliente") or "Cliente"
        dias = entry.get("dias_ate_vencimento")
        valor = entry.get("valor")
        vencimento = entry.get("vencimento")
        # Usar whatsapp do cliente como client_id proxy para window_key (sem UUID aqui)
        wpp = entry.get("whatsapp") or client_name
        window_key = f"{today_str}_{INITIATIVE_TYPE}_{wpp.replace('+', '').replace(' ', '')}"

        already_sent = await _check_already_sent_generic(window_key)
        if already_sent:
            results["skipped_spam"] += 1
            continue

        urgency = "\U0001f534 URGENTE" if dias == 0 else ("\U0001f7e1 Aten\u00e7\u00e3o" if dias <= 2 else "\U0001f7e2 Aviso")

        msg = (
            f"{urgency} \u2014 Vencimento Pr\u00f3ximo\n\n"
            f"*{client_name}* vence em {dias} dia(s) ({vencimento}).\n"
            f"Valor: R${float(valor):.2f}\n\n"
            f"Houve contato recente com esse cliente? Quer que eu prepare uma mensagem de lembrete?"
        )

        try:
            zapi_resp = await asyncio.to_thread(send_whatsapp_text, settings.mauro_whatsapp, msg)
            await _log_generic(window_key, INITIATIVE_TYPE, None, client_name, msg, zapi_resp)
            results["sent"] += 1
        except Exception as e:
            print(f"[friday_billing] falha ao enviar para {client_name}: {e}")
            results["errors"] += 1

    return {"message": f"Billing risk conclu\u00eddo: {results}"}


async def _check_already_sent_generic(window_key: str) -> bool:
    try:
        r = await asyncio.to_thread(
            lambda: supabase.table("friday_initiative_log")
            .select("id").eq("window_key", window_key).maybe_single().execute()
        )
        return bool(r.data)
    except Exception:
        return False


async def _log_generic(window_key, initiative_type, client_id, client_name, msg, zapi_resp):
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
        print(f"[friday_initiative] log falhou {window_key}: {e}")
