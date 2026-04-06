"""
LIFECYCLE-3.3 — Script Renderer with full context.
Renders upsell scripts with complete client data and delivers via Friday.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase
from runtime.expansion.scripts import get_script, list_script_types
from runtime.config import settings

logger = logging.getLogger(__name__)


async def _get_client_context(client_id: str) -> dict:
    client_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, client_id, business_name, business_type, display_slug, created_at, tier")
        .eq("id", client_id).maybe_single().execute()
    )
    client = client_res.data if client_res and hasattr(client_res, "data") else client_res
    if not client:
        return {}

    months_active = 0
    if client.get("created_at"):
        dt = datetime.fromisoformat(client["created_at"].replace("Z", "+00:00"))
        months_active = max(1, (datetime.now(timezone.utc) - dt).days // 30)

    health_res = await asyncio.to_thread(
        lambda: supabase.table("client_health")
        .select("score").eq("client_id", client_id)
        .order("calculated_at", desc=True).limit(1).execute()
    )
    health = (health_res.data or [{}])[0]
    score = health.get("score", "N/A")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    vol_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_events")
        .select("id", count="exact").eq("client_id", client_id)
        .gte("created_at", cutoff).execute()
    )
    volume = vol_res.count or 0

    return {
        "client_name": client.get("business_name", ""),
        "business_name": client.get("business_name", ""),
        "current_plan": client.get("tier", "Standard"),
        "health_score": score,
        "months_active": months_active,
        "niche": client.get("business_type", "varejo"),
        "zenya_name": client.get("display_slug", "Zenya"),
        "volume": volume,
    }


async def render_script_for_client(client_id: str, opportunity_type: str) -> dict:
    context = await _get_client_context(client_id)
    if not context:
        return {"error": "Client not found"}

    script = get_script(opportunity_type, context)
    if "error" in script:
        return script

    unresolved = [k for k, v in script.items() if isinstance(v, str) and "{" in v]

    return {
        "client_id": client_id, "opportunity_type": opportunity_type,
        "script": script, "context": context, "unresolved_variables": unresolved,
    }


async def deliver_script_to_friday(client_id: str, opportunity_type: str, opportunity_id: str = None) -> dict:
    rendered = await render_script_for_client(client_id, opportunity_type)
    if "error" in rendered:
        return rendered

    script = rendered["script"]
    ctx = rendered["context"]

    full_text = (
        f"Script de Upsell - {opportunity_type}\n"
        f"Cliente: {ctx.get('client_name', '?')}\n"
        f"Health Score: {ctx.get('health_score', '?')}\n"
        f"Meses ativo: {ctx.get('months_active', '?')}\n"
        f"Volume mensal: {ctx.get('volume', '?')}\n\n"
        f"---\n\n"
        f"Opening:\n{script.get('opening', '')}\n\n"
        f"Value Prop:\n{script.get('value_prop', '')}\n\n"
        f"CTA:\n{script.get('cta', '')}\n\n"
    )

    if script.get("objection_handlers"):
        full_text += "Respostas a objecoes:\n"
        for obj_type, response in script["objection_handlers"].items():
            full_text += f"- {obj_type}: {response}\n"

    try:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": getattr(settings, "sparkle_internal_client_id", None),
                "task_type": "friday_alert",
                "payload": {
                    "alert": "upsell_script_ready",
                    "client_id": client_id,
                    "client_name": ctx.get("client_name", ""),
                    "opportunity_type": opportunity_type,
                    "opportunity_id": opportunity_id,
                    "script_preview": full_text[:500],
                    "message": f"Script de {opportunity_type} pronto para {ctx.get('client_name')}. Revisar e enviar?",
                },
                "status": "pending", "priority": 6,
            }).execute()
        )
    except Exception as e:
        logger.error("[script_renderer] friday delivery failed: %s", e)

    return {
        "status": "delivered_to_friday", "client_id": client_id,
        "opportunity_type": opportunity_type, "script_text": full_text,
    }
