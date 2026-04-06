"""
LIFECYCLE-3.4 — Referral Engine.
Identifies promoters (NPS 9-10), proposes referral with mutual discount, tracks lifecycle.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)


async def _get_promoters() -> list[dict]:
    res = await asyncio.to_thread(
        lambda: supabase.table("client_nps")
        .select("client_id, score, collected_at")
        .gte("score", 9).order("collected_at", desc=True).execute()
    )
    rows = res.data or []
    seen = set()
    promoters = []
    for r in rows:
        cid = r["client_id"]
        if cid not in seen:
            seen.add(cid)
            promoters.append(r)
    return promoters


async def _has_active_referral(client_id: str) -> bool:
    res = await asyncio.to_thread(
        lambda: supabase.table("referrals")
        .select("id", count="exact").eq("referrer_id", client_id)
        .in_("status", ["proposed", "accepted"]).execute()
    )
    return (res.count or 0) > 0


async def propose_referral(client_id: str) -> dict:
    if await _has_active_referral(client_id):
        return {"status": "already_proposed", "client_id": client_id}

    client_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, business_name, phone_number")
        .eq("id", client_id).maybe_single().execute()
    )
    client = client_res.data if client_res and hasattr(client_res, "data") else client_res
    if not client:
        return {"error": "Client not found"}

    name = client.get("business_name", "")
    phone = client.get("phone_number", "")

    ref_res = await asyncio.to_thread(
        lambda: supabase.table("referrals").insert({
            "referrer_id": client_id, "status": "proposed",
        }).execute()
    )
    ref_id = (ref_res.data or [{}])[0].get("id")

    msg = (
        f"Oi {name}!\n\n"
        f"Muito obrigado pela parceria e pela avaliacao positiva!\n\n"
        f"Temos um programa de indicacao:\n"
        f"- Voce indica um amigo empresario\n"
        f"- Ambos ganham 10% de desconto no proximo mes\n\n"
        f"E so mandar o nome e telefone do contato que a gente cuida do resto!"
    )

    if phone:
        try:
            from runtime.integrations.zapi import send_text
            await asyncio.to_thread(send_text, phone, msg)
        except Exception as e:
            logger.error("[referral] Z-API send failed: %s", e)

    return {"status": "proposed", "referral_id": ref_id, "client_name": name}


async def register_referred_lead(referral_id: str, name: str, phone: str) -> dict:
    lead_res = await asyncio.to_thread(
        lambda: supabase.table("leads").insert({
            "name": name, "phone": phone, "source": "referral", "status": "new",
        }).execute()
    )
    lead = (lead_res.data or [{}])[0]
    lead_id = lead.get("id")

    ref_res = await asyncio.to_thread(
        lambda: supabase.table("referrals")
        .select("referrer_id").eq("id", referral_id).maybe_single().execute()
    )
    ref_data = ref_res.data if ref_res and hasattr(ref_res, "data") else ref_res
    referrer_id = ref_data.get("referrer_id") if ref_data else None

    if lead_id and referrer_id:
        await asyncio.to_thread(
            lambda: supabase.table("leads")
            .update({"referred_by": referrer_id}).eq("id", lead_id).execute()
        )

    await asyncio.to_thread(
        lambda: supabase.table("referrals").update({
            "referred_lead_id": lead_id, "referred_name": name,
            "referred_phone": phone, "status": "accepted",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", referral_id).execute()
    )

    return {"referral_id": referral_id, "lead_id": lead_id, "status": "accepted"}


async def mark_referral_converted(referral_id: str) -> dict:
    await asyncio.to_thread(
        lambda: supabase.table("referrals").update({
            "status": "converted",
            "converted_at": datetime.now(timezone.utc).isoformat(),
            "discount_applied": True,
        }).eq("id", referral_id).execute()
    )

    ref_res = await asyncio.to_thread(
        lambda: supabase.table("referrals")
        .select("referrer_id, referred_name")
        .eq("id", referral_id).maybe_single().execute()
    )
    ref = ref_res.data if ref_res and hasattr(ref_res, "data") else ref_res

    if ref:
        c_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("business_name").eq("id", ref["referrer_id"]).maybe_single().execute()
        )
        c_data = c_res.data if c_res and hasattr(c_res, "data") else c_res
        referrer_name = c_data.get("business_name", "?") if c_data else "?"

        try:
            await asyncio.to_thread(
                lambda: supabase.table("runtime_tasks").insert({
                    "agent_id": "friday",
                    "client_id": getattr(settings, "sparkle_internal_client_id", None),
                    "task_type": "friday_alert",
                    "payload": {
                        "alert": "referral_converted", "referrer": referrer_name,
                        "referred": ref.get("referred_name", "?"),
                        "message": f"Referral convertido! {referrer_name} indicou {ref.get('referred_name', '?')} e ambos ganham 10% de desconto.",
                    },
                    "status": "pending", "priority": 8,
                }).execute()
            )
        except Exception as e:
            logger.error("[referral] friday notify failed: %s", e)

    return {"referral_id": referral_id, "status": "converted"}


async def propose_to_all_promoters() -> dict:
    promoters = await _get_promoters()
    proposed = 0
    skipped = 0

    for p in promoters:
        result = await propose_referral(p["client_id"])
        if result.get("status") == "proposed":
            proposed += 1
        else:
            skipped += 1

    logger.info("[referral] proposed=%d skipped=%d", proposed, skipped)
    return {"promoters_found": len(promoters), "proposed": proposed, "skipped": skipped}
