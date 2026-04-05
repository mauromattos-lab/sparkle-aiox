"""
Cockpit router — /cockpit/* endpoints.

POST /cockpit/summary  — trigger cockpit summary and send to Mauro via WhatsApp
GET  /cockpit/summary  — generate preview (no send)

GET  /cockpit/overview  — JSON overview for Portal dashboard
GET  /cockpit/clients   — client list with health for Portal
GET  /cockpit/agents    — active agents with last task for Portal
GET  /cockpit/activity  — last 50 runtime events for Portal

Both summary endpoints work by creating a runtime_task and executing it inline,
following the same pattern used throughout the runtime.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.handlers.cockpit_summary import (
    handle_cockpit_summary,
    handle_cockpit_query,
    _fetch_clients,
    _fetch_brain_stats,
    _fetch_task_stats,
    _enrich_client_health,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cockpit", tags=["cockpit"])


@router.post("/summary")
async def trigger_cockpit_summary():
    """
    Trigger a cockpit summary and send to Mauro via WhatsApp.

    Creates a task in runtime_tasks for auditability, then executes inline.
    """
    # Create task record for auditability
    task: dict = {"task_type": "cockpit_summary", "triggered_by": "api"}
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "cockpit_summary",
                "payload": {"triggered_by": "api_manual"},
                "status": "pending",
                "priority": 7,
            }).execute()
        )
        if res.data:
            task = res.data[0]
    except Exception as e:
        print(f"[cockpit_router] failed to create task record: {e}")

    result = await handle_cockpit_summary(task)

    return {
        "status": "sent" if result.get("sent") else "generated",
        "message": result.get("message"),
        "sent_to": settings.mauro_whatsapp if result.get("sent") else None,
    }


@router.get("/summary")
async def preview_cockpit_summary():
    """
    Generate a cockpit summary preview without sending to WhatsApp.
    Useful for testing and dashboards.
    """
    task: dict = {"task_type": "cockpit_query", "triggered_by": "api_preview"}
    result = await handle_cockpit_query(task)

    return {
        "status": "preview",
        "message": result.get("message"),
    }


# ── Portal JSON endpoints ────────────────────────────────────


@router.get("/overview")
async def cockpit_overview() -> dict[str, Any]:
    """
    Executive overview for the Portal dashboard.

    Returns MRR, client count, brain stats, 24h task stats,
    agent counts, and current UTC timestamp.
    """
    now_utc = datetime.now(timezone.utc)
    cutoff_24h = (now_utc - timedelta(hours=24)).isoformat()

    # Run all queries in parallel
    clients_raw, brain, tasks_24h, agents_data = await asyncio.gather(
        _fetch_clients(),
        _fetch_brain_stats(),
        _fetch_task_stats(cutoff_24h),
        _fetch_agents(),
    )

    # MRR — exclude sparkle-internal
    active = [
        c for c in clients_raw
        if c.get("status") == "active" and c.get("id") != settings.sparkle_internal_client_id
    ]
    total_mrr = sum(float(c.get("mrr") or 0) for c in active)

    # Agent counts
    total_agents = len(agents_data)
    active_agents = sum(1 for a in agents_data if (a.get("status") or "").lower() == "active")

    return {
        "mrr": total_mrr,
        "client_count": len(active),
        "brain": brain,
        "tasks_24h": {
            "total": tasks_24h.get("total", 0),
            "done": tasks_24h.get("completed", 0),
            "failed": tasks_24h.get("failed", 0),
        },
        "agents": {
            "total": total_agents,
            "active": active_agents,
        },
        "timestamp": now_utc.isoformat(),
    }


@router.get("/clients")
async def cockpit_clients() -> dict[str, Any]:
    """
    Client list with health status for the Portal.

    For each active client returns: client_id, name, company, mrr, plan,
    has_zenya, health_status (green/yellow/red), last_activity.
    """
    now_utc = datetime.now(timezone.utc)

    clients_raw = await _fetch_clients_full()
    clients_with_health = await _enrich_client_health(clients_raw, now_utc)

    result: list[dict[str, Any]] = []
    for c in clients_with_health:
        # Skip internal
        if c.get("id") == settings.sparkle_internal_client_id:
            continue
        result.append({
            "client_id": c.get("id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "mrr": float(c.get("mrr") or 0),
            "plan": c.get("plan"),
            "has_zenya": c.get("has_zenya", False),
            "health_status": c.get("_health", "green"),
            "last_activity": c.get("updated_at"),
        })

    return {"clients": result, "count": len(result)}


@router.get("/agents")
async def cockpit_agents() -> dict[str, Any]:
    """
    Active agents with capabilities and last task for the Portal.

    Returns agent_id, display_name, agent_type, model, status,
    capabilities count, and last task info.
    """
    agents_data = await _fetch_agents()

    # Collect all agent_ids to batch-fetch last tasks
    agent_ids = [a.get("agent_id") for a in agents_data if a.get("agent_id")]
    last_tasks = await _fetch_last_tasks_by_agents(agent_ids)

    result: list[dict[str, Any]] = []
    for a in agents_data:
        aid = a.get("agent_id", "")
        caps = a.get("capabilities") or a.get("skills") or []
        caps_count = len(caps) if isinstance(caps, list) else 0

        last_task = last_tasks.get(aid)

        result.append({
            "agent_id": aid,
            "display_name": a.get("display_name") or a.get("name", aid),
            "agent_type": a.get("agent_type"),
            "model": a.get("model"),
            "status": a.get("status", "active"),
            "capabilities_count": caps_count,
            "last_task": last_task,
        })

    return {"agents": result, "count": len(result)}


@router.get("/activity")
async def cockpit_activity() -> dict[str, Any]:
    """
    Last 50 runtime events for the Portal activity feed.

    Returns id, task_type, agent_id, status, created_at, and a
    truncated payload summary (first 100 chars).
    """
    events = await _fetch_recent_activity(limit=50)
    return {"events": events, "count": len(events)}


# ── Data fetchers (Portal-specific) ─────────────────────────


async def _fetch_clients_full() -> list[dict]:
    """Fetch active clients with extended fields for Portal."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,company,mrr,plan,status,has_zenya,whatsapp,updated_at")
            .eq("status", "active")
            .order("mrr", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("[cockpit/clients] failed to fetch clients: %s", e)
        return []


async def _fetch_agents() -> list[dict]:
    """Fetch all active agents from the agents table."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("agents")
            .select("agent_id,name,display_name,agent_type,model,status,capabilities,skills")
            .eq("status", "active")
            .order("agent_id")
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("[cockpit/agents] failed to fetch agents: %s", e)
        return []


async def _fetch_last_tasks_by_agents(agent_ids: list[str]) -> dict[str, dict | None]:
    """
    For a list of agent_ids, fetch the most recent runtime_task for each.

    Returns a dict mapping agent_id -> {id, task_type, status, created_at} or None.
    """
    if not agent_ids:
        return {}

    result: dict[str, dict | None] = {aid: None for aid in agent_ids}

    try:
        # Fetch recent tasks for all requested agents, ordered by created_at desc.
        # We fetch more than needed and deduplicate in Python to avoid N+1 queries.
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,agent_id,task_type,status,created_at")
            .in_("agent_id", agent_ids)
            .order("created_at", desc=True)
            .limit(len(agent_ids) * 3)  # heuristic: enough to cover all agents
            .execute()
        )
        rows = res.data or []

        # Keep only the first (most recent) task per agent
        for row in rows:
            aid = row.get("agent_id")
            if aid and aid in result and result[aid] is None:
                result[aid] = {
                    "id": row.get("id"),
                    "task_type": row.get("task_type"),
                    "status": row.get("status"),
                    "created_at": row.get("created_at"),
                }
    except Exception as e:
        logger.error("[cockpit/agents] failed to fetch last tasks: %s", e)

    return result


async def _fetch_recent_activity(limit: int = 50) -> list[dict]:
    """Fetch the most recent runtime_tasks for the activity feed."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,task_type,agent_id,status,created_at,payload")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = res.data or []

        events: list[dict] = []
        for row in rows:
            # Truncate payload to a summary string
            payload = row.get("payload")
            if isinstance(payload, dict):
                summary = str(payload)[:100]
            elif isinstance(payload, str):
                summary = payload[:100]
            else:
                summary = ""

            events.append({
                "id": row.get("id"),
                "task_type": row.get("task_type"),
                "agent_id": row.get("agent_id"),
                "status": row.get("status"),
                "created_at": row.get("created_at"),
                "payload_summary": summary,
            })

        return events
    except Exception as e:
        logger.error("[cockpit/activity] failed to fetch activity: %s", e)
        return []
