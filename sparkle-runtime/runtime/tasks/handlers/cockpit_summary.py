"""
Cockpit Summary — TIER 1 executive view for Friday.

Aggregates the state of the entire Sparkle AIOX system into a single
WhatsApp message: MRR, client health, Brain stats, system tasks and alerts.

Handlers:
  handle_cockpit_summary(task) — builds & sends via Z-API to MAURO_WHATSAPP
  handle_cockpit_query(task)   — builds & returns as text (for Friday replies)

Cron: daily at 11h UTC (8h BRT) via scheduler.
REST: POST /cockpit/summary  → send
      GET  /cockpit/summary  → preview (no send)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from runtime.config import settings
from runtime.db import supabase

_TZ = ZoneInfo("America/Sao_Paulo")

# ── Thresholds for client health ─────────────────────────────
_YELLOW_HOURS = 24   # >24h without Zenya activity → yellow
_RED_HOURS    = 72   # >72h without Zenya activity → red

# ── Active cron count (mirrors scheduler.py — update if crons change) ──────
_ACTIVE_CRONS = 14  # includes cockpit_summary added here


# ── Public handlers ──────────────────────────────────────────

async def handle_cockpit_summary(task: dict) -> dict:
    """Builds the cockpit message and sends to Mauro via WhatsApp."""
    message = await _build_cockpit_message()

    if settings.mauro_whatsapp:
        try:
            from runtime.integrations.zapi import send_text
            await asyncio.to_thread(send_text, settings.mauro_whatsapp, message)
        except Exception as e:
            print(f"[cockpit_summary] failed to send WhatsApp: {e}")

    return {"message": message, "sent": bool(settings.mauro_whatsapp)}


async def handle_cockpit_query(task: dict) -> dict:
    """Builds the cockpit message and returns it as text (no send)."""
    message = await _build_cockpit_message()
    return {"message": message, "sent": False}


# ── Core builder ─────────────────────────────────────────────

async def _build_cockpit_message() -> str:
    """Aggregates all TIER 1 data and formats the WhatsApp message."""
    now_brt = datetime.now(_TZ)
    now_utc = datetime.now(timezone.utc)
    cutoff_24h = (now_utc - timedelta(hours=24)).isoformat()

    # Run all queries in parallel
    clients_data, brain_stats, task_stats = await asyncio.gather(
        _fetch_clients(),
        _fetch_brain_stats(),
        _fetch_task_stats(cutoff_24h),
    )

    # Fetch last activity per client (sequential is fine — small dataset)
    clients_with_health = await _enrich_client_health(clients_data, now_utc)

    # MRR
    active_clients = [c for c in clients_with_health if c.get("status") == "active"]
    total_mrr = sum(float(c.get("mrr") or 0) for c in active_clients)
    # Exclude internal Sparkle client from public count
    billing_clients = [c for c in active_clients if c.get("name", "").lower() not in ("mauro mattos",)]
    n_billing = len(billing_clients)

    # Format MRR in BR style
    mrr_str = f"R${total_mrr:,.0f}".replace(",", ".")

    # Alerts
    alerts: list[str] = []
    red_clients = [c for c in clients_with_health if c["_health"] == "red"]
    for c in red_clients:
        hours = c.get("_inactive_hours", 0)
        alerts.append(f"⛔ {c['name']} — sem atividade há {hours}h")

    failed_count = task_stats.get("failed", 0)
    if failed_count >= 5:
        alerts.append(f"⚠️ {failed_count} tasks falharam nas últimas 24h")

    # ── Build message ────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"🏢 COCKPIT SPARKLE — {now_brt.strftime('%d/%m %H:%M')}")
    lines.append("")
    lines.append(f"💰 MRR: {mrr_str}/mês ({n_billing} clientes)")
    lines.append("")
    lines.append("👥 CLIENTES:")

    for c in clients_with_health:
        # Skip internal Sparkle entry
        if c.get("name", "").lower() in ("mauro mattos",):
            continue
        icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(c["_health"], "⚪")
        mrr_val = float(c.get("mrr") or 0)
        health_note = c["_health_note"]
        lines.append(f"{icon} {c['name']} (R${mrr_val:,.0f}) — {health_note}".replace(",", "."))

    lines.append("")

    # Brain
    approved = brain_stats.get("approved", 0)
    pending  = brain_stats.get("pending", 0)
    review   = brain_stats.get("review", 0)
    total_chunks = approved + pending + review + brain_stats.get("rejected", 0)
    lines.append(f"🧠 BRAIN: {approved} aprovados / {pending} pendentes / {review} em revisão")
    lines.append("")

    # System 24h
    completed = task_stats.get("completed", 0)
    failed    = task_stats.get("failed", 0)
    total_tasks = task_stats.get("total", 0)
    lines.append(f"⚡ SISTEMA 24h: {completed} tasks ok / {failed} falhas / {_ACTIVE_CRONS} crons ativos")
    lines.append("")

    # Alerts
    alert_count = len(alerts)
    if alert_count == 0:
        lines.append("🔔 ALERTAS: nenhum — tudo ok ✅")
    else:
        lines.append(f"🔔 ALERTAS: {alert_count}")
        for alert in alerts:
            lines.append(f"  {alert}")

    lines.append("")
    lines.append("— Friday 🤖")

    return "\n".join(lines)


# ── Data fetchers ─────────────────────────────────────────────

async def _fetch_clients() -> list[dict]:
    """Fetch active clients from Supabase."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,mrr,status,has_zenya,whatsapp,updated_at")
            .eq("status", "active")
            .order("mrr", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[cockpit_summary] failed to fetch clients: {e}")
        return []


async def _fetch_brain_stats() -> dict[str, int]:
    """Fetch brain_chunks grouped by curation_status."""
    stats: dict[str, int] = {
        "pending": 0, "approved": 0, "review": 0, "rejected": 0
    }
    try:
        # Fetch all curation_status values with a simple select
        res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("curation_status")
            .execute()
        )
        rows = res.data or []
        for row in rows:
            s = (row.get("curation_status") or "pending").lower()
            stats[s] = stats.get(s, 0) + 1
    except Exception as e:
        print(f"[cockpit_summary] failed to fetch brain stats: {e}")
    return stats


async def _fetch_task_stats(cutoff_iso: str) -> dict[str, int]:
    """Fetch runtime_tasks stats for the last 24h."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("status")
            .gte("created_at", cutoff_iso)
            .execute()
        )
        rows = res.data or []
        total     = len(rows)
        completed = sum(1 for r in rows if r.get("status") in ("done", "completed"))
        failed    = sum(1 for r in rows if r.get("status") == "failed")
        return {"total": total, "completed": completed, "failed": failed}
    except Exception as e:
        print(f"[cockpit_summary] failed to fetch task stats: {e}")
        return {"total": 0, "completed": 0, "failed": 0}


async def _enrich_client_health(
    clients: list[dict],
    now_utc: datetime,
) -> list[dict]:
    """
    For each client that has_zenya, look up the last conversation message
    and tag with green/yellow/red based on inactivity thresholds.
    Clients without Zenya default to green (health is N/A).
    """
    enriched: list[dict] = []

    for client in clients:
        c = dict(client)

        if not c.get("has_zenya"):
            c["_health"] = "green"
            c["_health_note"] = "ativo (sem Zenya)"
            c["_inactive_hours"] = 0
            enriched.append(c)
            continue

        # Try to find last conversation message for this client
        inactive_hours = 0
        try:
            res = await asyncio.to_thread(
                lambda cid=c["id"]: supabase.table("conversation_history")
                .select("created_at")
                .eq("client_id", cid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if rows:
                last_ts_str = rows[0].get("created_at", "")
                # Parse ISO timestamp
                if last_ts_str:
                    try:
                        last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
                        inactive_hours = int((now_utc - last_ts).total_seconds() / 3600)
                    except Exception:
                        inactive_hours = 0
            else:
                # No conversations at all — treat as very inactive
                inactive_hours = 999
        except Exception as e:
            print(f"[cockpit_summary] health check failed for {c.get('name')}: {e}")
            inactive_hours = 0

        c["_inactive_hours"] = inactive_hours

        if inactive_hours == 0 or inactive_hours < _YELLOW_HOURS:
            c["_health"] = "green"
            c["_health_note"] = "ativo"
        elif inactive_hours < _RED_HOURS:
            c["_health"] = "yellow"
            c["_health_note"] = f"sem atividade {inactive_hours}h"
        else:
            c["_health"] = "red"
            if inactive_hours >= 999:
                c["_health_note"] = "sem conversas registradas"
            else:
                c["_health_note"] = f"sem atividade {inactive_hours}h"

        enriched.append(c)

    return enriched
