"""
Iniciativa 3: Oportunidade de Upsell — cliente com Zenya mas sem tráfego, ou com tráfego mas sem Zenya.

Query: clients WHERE (has_zenya=true AND has_trafego=false) OR (has_zenya=false AND has_trafego=true)
       AND status='ativo'

Cron: semanal, segunda-feira às 7h30 Brasília (antes do gap_report das 8h).
Anti-spam: window_key semanal (usa ISO week) por cliente.
"""
from __future__ import annotations

import asyncio
from datetime import date

from runtime.db import supabase
from runtime.config import settings
from runtime.integrations.zapi import send_text as send_whatsapp_text


INITIATIVE_TYPE = "upsell_opportunity"


async def handle_friday_initiative_upsell(task: dict) -> dict:
    results = {"sent": 0, "skipped_spam": 0, "errors": 0}
    iso_week = date.today().strftime("%Y-W%V")  # ex: 2026-W14

    try:
        # Clientes com gap de produto
        clients_resp = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id, name, company, mrr, has_zenya, has_trafego, status")
            .eq("status", "ativo")
            .execute()
        )
        all_clients = clients_resp.data or []
    except Exception as e:
        return {"message": f"Upsell initiative erro: {e}"}

    # Filtrar clientes com gap de produto
    opportunities = [
        c for c in all_clients
        if (c.get("has_zenya") and not c.get("has_trafego"))
        or (not c.get("has_zenya") and c.get("has_trafego"))
    ]

    for client in opportunities:
        client_id = client.get("id")
        client_name = client.get("name") or client.get("company") or "Cliente"
        has_zenya = client.get("has_zenya", False)
        has_trafego = client.get("has_trafego", False)
        mrr = client.get("mrr") or 0

        window_key = f"{iso_week}_{INITIATIVE_TYPE}_{client_id}"

        already_sent = await _check_spam(window_key)
        if already_sent:
            results["skipped_spam"] += 1
            continue

        # Calcular oportunidade
        if has_zenya and not has_trafego:
            missing = "tr\u00e1fego pago"
            potential_mrr = mrr + 750  # preco medio do plano de trafego
            arg = "j\u00e1 tem Zenya (atendimento) mas n\u00e3o tem tr\u00e1fego \u2014 perfeito para escalar com an\u00fancios"
        else:
            missing = "Zenya"
            potential_mrr = mrr + 500  # preco medio do plano Zenya
            arg = "j\u00e1 tem tr\u00e1fego mas n\u00e3o tem Zenya \u2014 leads chegando sem atendimento autom\u00e1tico"

        msg = (
            f"\U0001f4a1 *Oportunidade de Upsell \u2014 {client_name}*\n\n"
            f"Esse cliente {arg}.\n\n"
            f"MRR atual: R${float(mrr):.2f} \u2192 Potencial com {missing}: R${float(potential_mrr):.2f}\n\n"
            f"Quer que eu prepare uma proposta ou agende um contato esta semana?"
        )

        try:
            zapi_resp = await asyncio.to_thread(send_whatsapp_text, settings.mauro_whatsapp, msg)
            await _log_upsell(window_key, client_id, client_name, msg, zapi_resp)
            results["sent"] += 1
        except Exception as e:
            print(f"[friday_upsell] falha ao enviar para {client_name}: {e}")
            results["errors"] += 1

    return {"message": f"Upsell initiative conclu\u00eddo: {results}"}


async def _check_spam(window_key: str) -> bool:
    try:
        r = await asyncio.to_thread(
            lambda: supabase.table("friday_initiative_log")
            .select("id").eq("window_key", window_key).maybe_single().execute()
        )
        return bool(r.data)
    except Exception:
        return False


async def _log_upsell(window_key, client_id, client_name, msg, zapi_resp):
    try:
        await asyncio.to_thread(
            lambda: supabase.table("friday_initiative_log").insert({
                "initiative_type": INITIATIVE_TYPE,
                "client_id": str(client_id),
                "client_name": client_name,
                "window_key": window_key,
                "message_preview": msg[:200],
                "zapi_response": zapi_resp if isinstance(zapi_resp, dict) else {"raw": str(zapi_resp)},
            }).execute()
        )
    except Exception as e:
        print(f"[friday_upsell] log falhou: {e}")
