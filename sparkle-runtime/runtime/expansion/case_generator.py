"""
LIFECYCLE-3.4 — Automatic Case Generator.
Generates success cases from real client metrics for healthy, authorized clients.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)


async def _get_eligible_clients() -> list[dict]:
    auth_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, business_name, business_type, created_at")
        .eq("active", True).eq("case_authorized", True).execute()
    )
    clients = auth_res.data or []
    eligible = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()

    for client in clients:
        cid = client["id"]
        health_res = await asyncio.to_thread(
            lambda cid=cid: supabase.table("client_health")
            .select("score, calculated_at").eq("client_id", cid)
            .gte("calculated_at", cutoff).order("calculated_at", desc=False).execute()
        )
        scores = health_res.data or []
        if len(scores) < 6:
            continue
        if all(s.get("score", 0) > 70 for s in scores):
            client["avg_score"] = sum(s["score"] for s in scores) // len(scores)
            eligible.append(client)

    return eligible


async def _already_has_case(client_id: str) -> bool:
    res = await asyncio.to_thread(
        lambda: supabase.table("auto_cases")
        .select("id", count="exact").eq("client_id", client_id).execute()
    )
    return (res.count or 0) > 0


async def _get_client_metrics(client_id: str) -> dict:
    now = datetime.now(timezone.utc)
    month_ago = (now - timedelta(days=30)).isoformat()
    vol_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_events")
        .select("id", count="exact").eq("client_id", client_id)
        .gte("created_at", month_ago).execute()
    )
    current_volume = vol_res.count or 0

    client_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("created_at").eq("id", client_id).maybe_single().execute()
    )
    c_data = client_res.data if client_res and hasattr(client_res, "data") else client_res
    first_month_end = None
    if c_data and c_data.get("created_at"):
        start = datetime.fromisoformat(c_data["created_at"].replace("Z", "+00:00"))
        first_month_end = (start + timedelta(days=30)).isoformat()

    first_volume = 0
    if first_month_end:
        fv_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_events")
            .select("id", count="exact").eq("client_id", client_id)
            .lte("created_at", first_month_end).execute()
        )
        first_volume = fv_res.count or 0

    ttv_res = await asyncio.to_thread(
        lambda: supabase.table("client_milestones")
        .select("ttv_days").eq("client_id", client_id)
        .eq("milestone_type", "first_real_message").maybe_single().execute()
    )
    ttv_data = ttv_res.data if ttv_res and hasattr(ttv_res, "data") else ttv_res
    ttv_days = ttv_data.get("ttv_days") if ttv_data else None

    hs_res = await asyncio.to_thread(
        lambda: supabase.table("client_health")
        .select("score").eq("client_id", client_id)
        .order("calculated_at", desc=True).limit(1).execute()
    )
    health = (hs_res.data or [{}])[0].get("score", 0)

    nps_res = await asyncio.to_thread(
        lambda: supabase.table("client_nps")
        .select("score, feedback").eq("client_id", client_id)
        .order("collected_at", desc=True).limit(1).execute()
    )
    nps = (nps_res.data or [{}])[0] if nps_res.data else {}

    return {
        "current_monthly_volume": current_volume,
        "first_month_volume": first_volume,
        "volume_growth_pct": round((current_volume / max(first_volume, 1) - 1) * 100),
        "ttv_days": ttv_days,
        "health_score": health,
        "nps_score": nps.get("score"),
        "nps_quote": nps.get("feedback"),
    }


async def generate_case(client_id: str) -> dict:
    if await _already_has_case(client_id):
        return {"status": "already_exists", "client_id": client_id}

    client_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, business_name, business_type, display_slug, created_at")
        .eq("id", client_id).maybe_single().execute()
    )
    client = client_res.data if client_res and hasattr(client_res, "data") else client_res
    if not client:
        return {"error": "Client not found"}

    metrics = await _get_client_metrics(client_id)
    name = client.get("business_name", "")
    niche = client.get("business_type", "varejo")
    zenya = client.get("display_slug", "Zenya")

    months = 0
    if client.get("created_at"):
        dt = datetime.fromisoformat(client["created_at"].replace("Z", "+00:00"))
        months = max(1, (datetime.now(timezone.utc) - dt).days // 30)

    title = f"{name} - {niche.title() if niche else 'Varejo'}"

    parts = [
        f"## {name}",
        f"**Nicho:** {niche or 'Varejo'} | **Zenya:** {zenya} | **Cliente ha:** {months} meses",
        "",
        "### Desafio",
        f"{name} precisava de atendimento consistente no WhatsApp sem depender de equipe 24/7.",
        "",
        "### Solucao",
        f"Implementamos a {zenya}, assistente IA personalizada que atende clientes com a voz da marca.",
        "",
        "### Resultados",
        f"- Volume mensal: {metrics['first_month_volume']} -> {metrics['current_monthly_volume']} atendimentos ({metrics['volume_growth_pct']:+d}%)",
    ]

    if metrics.get("ttv_days"):
        parts.append(f"- Time-to-Value: {metrics['ttv_days']} dias do contrato ao primeiro atendimento real")
    parts.append(f"- Health Score: {metrics['health_score']}/100")
    if metrics.get("nps_score") is not None:
        parts.append(f"- NPS: {metrics['nps_score']}/10")

    quote = metrics.get("nps_quote", "")
    if quote:
        parts.extend(["", "### Depoimento", f'> "{quote}" - {name}'])

    content = "\n".join(parts)

    case_res = await asyncio.to_thread(
        lambda: supabase.table("auto_cases").insert({
            "client_id": client_id, "niche": niche, "title": title,
            "content": content, "metrics": metrics,
            "quote": quote or None, "status": "draft",
        }).execute()
    )
    case_id = (case_res.data or [{}])[0].get("id")

    logger.info("[case_gen] case generated for %s: %s", name, case_id)
    return {"case_id": case_id, "client_id": client_id, "title": title, "status": "draft"}


async def generate_all_eligible_cases() -> dict:
    eligible = await _get_eligible_clients()
    generated = 0
    skipped = 0

    for client in eligible:
        result = await generate_case(client["id"])
        if result.get("case_id"):
            generated += 1
        else:
            skipped += 1

    logger.info("[case_gen] eligible=%d generated=%d skipped=%d", len(eligible), generated, skipped)
    return {"eligible": len(eligible), "generated": generated, "skipped": skipped}
