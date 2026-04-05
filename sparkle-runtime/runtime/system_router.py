"""
System router — /system/* endpoints.

GET  /system/capabilities — lista handlers, domains, agents, crons, brain_stats
GET  /system/state        — consulta estado de sprint items (agent_work_items)
POST /system/state        — grava conclusão de sprint item

Permite que agentes construtores entendam o que já existe antes de propor mudanças:
    GET /system/capabilities → entender o que já existe → propor só o que falta
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.config import settings
from runtime.tasks.registry import REGISTRY

router = APIRouter(prefix="/system", tags=["system"])

# ── Constantes descritivas ──────────────────────────────────

_DOMAINS = [
    "trafego_pago",
    "zenya_config",
    "conteudo",
    "estrategia",
    "financeiro",
    "tech",
    "brain_ops",
]

_AGENTS = sorted(["analyst", "architect", "dev", "qa", "pm", "trafego"])

_CRONS = [
    {"name": "health_check",          "schedule": "every 15min"},
    {"name": "daily_briefing",        "schedule": "daily 8h Brasilia"},
    {"name": "cockpit_summary",       "schedule": "daily 8h Brasilia (11h UTC)"},
    {"name": "weekly_briefing",       "schedule": "sunday 8h Brasilia"},
    {"name": "observer_gap_analysis", "schedule": "monday 8h Brasilia"},
    {"name": "daily_decision_moment", "schedule": "daily 9h Brasilia"},
    {"name": "billing_risk",          "schedule": "daily 8h45 Brasilia"},
    {"name": "risk_alert",            "schedule": "daily 9h30 Brasilia"},
    {"name": "upsell_opportunity",    "schedule": "monday 7h30 Brasilia"},
    {"name": "brain_weekly_digest",   "schedule": "sunday 23h Brasilia"},
    {"name": "content_weekly_batch",  "schedule": "monday 7h Brasilia"},
    {"name": "brain_archival",        "schedule": "daily 3h Brasilia"},
    {"name": "brain_curate_02h",      "schedule": "daily 2h UTC"},
    {"name": "brain_curate_10h",      "schedule": "daily 10h UTC"},
    {"name": "brain_curate_18h",      "schedule": "daily 18h UTC"},
    {"name": "client_dna_refresh",    "schedule": "monday 4h Brasilia"},
    {"name": "client_reports_monthly","schedule": "day 1 of month 10h UTC"},
    {"name": "onboarding_check_gates","schedule": "every 1h (ONB-1)"},
]

_VERSION = "sprint9"


# ── Helpers ─────────────────────────────────────────────────

async def _count_table(table: str) -> int:
    """Retorna count de uma tabela Supabase. Silencia erros."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table(table).select("id", count="exact").limit(1).execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        print(f"[system] count {table} failed: {e}")
        return -1


# ── Capabilities ────────────────────────────────────────────

@router.get("/capabilities")
async def get_capabilities():
    """
    Retorna snapshot completo das capacidades do Runtime.

    Usado por agentes construtores para entender o que já existe antes de propor mudanças:
        GET /system/capabilities → entender o que já existe → propor só o que falta
    """
    chunks_total, dna_entries = await asyncio.gather(
        _count_table("brain_chunks"),
        _count_table("agent_dna"),
    )

    return {
        "handlers": sorted(REGISTRY.keys()),
        "domains": _DOMAINS,
        "agents": _AGENTS,
        "crons": _CRONS,
        "brain_stats": {
            "chunks_total": chunks_total,
            "dna_entries": dna_entries,
        },
        "version": _VERSION,
    }


# ── State (sprint item tracking) ────────────────────────────

class StateUpdate(BaseModel):
    sprint_item: str
    status: str
    title: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    verified: bool = True
    verification_source: Optional[str] = None
    handoff_to: Optional[str] = None
    completed: bool = False


@router.post("/state")
async def update_state(update: StateUpdate):
    """
    Grava conclusão de sprint item em agent_work_items.

    Protocolo obrigatório ao concluir trabalho:
        POST /system/state com sprint_item, status, verified, notes, handoff_to
    """
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_key
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase nao configurado")

    payload: dict = {
        "status": update.status,
        "verified": update.verified,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if update.title:               payload["title"] = update.title
    if update.notes:               payload["notes"] = update.notes
    if update.verification_source: payload["verification_source"] = update.verification_source
    if update.handoff_to:          payload["handoff_to"] = update.handoff_to
    if update.assigned_to:         payload["assigned_to"] = update.assigned_to
    if update.completed:           payload["completed_at"] = datetime.now(timezone.utc).isoformat()

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{supabase_url}/rest/v1/agent_work_items",
            params={"sprint_item": f"eq.{update.sprint_item}"},
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code in (200, 204):
            data = resp.json()
            if not data:
                # Registro não existe — cria
                payload["sprint_item"] = update.sprint_item
                payload["created_by"] = update.assigned_to or "agent"
                if update.title: payload["title"] = update.title
                await client.post(
                    f"{supabase_url}/rest/v1/agent_work_items",
                    json=payload, headers=headers, timeout=10,
                )
                return {"action": "created", "sprint_item": update.sprint_item, "status": update.status}
            return {"action": "updated", "sprint_item": update.sprint_item, "status": update.status}
        raise HTTPException(status_code=resp.status_code, detail=resp.text)


# ── Pulse (consolidated dashboard endpoint) ────────────────


@router.get("/pulse")
async def get_pulse():
    """
    Endpoint consolidado para o Command Panel (SYS-6).

    Retorna:
      - agents: lista de agentes com status ao vivo
      - brain: chunks hoje, ultimas 5 ingestoes, total
      - workflows: instancias ativas, completadas hoje
      - clients: ativos, MRR total
      - timestamp
    """
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_key
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase nao configurado")

    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

    async def _fetch(path: str, params: dict) -> list:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/{path}",
                params=params,
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # Run all queries in parallel
    (
        running_tasks,
        recent_tasks,
        last_ingestions,
        active_workflows,
        active_clients,
        chunks_today_count,
        chunks_total_count,
        workflows_completed_today_count,
    ) = await asyncio.gather(
        # Tasks currently running (agents working)
        _fetch("runtime_tasks", {
            "select": "id,agent_id,task_type,status,created_at,payload",
            "status": "eq.running",
            "order": "created_at.desc",
            "limit": "20",
        }),
        # Recent tasks (last 24h) for agent activity
        _fetch("runtime_tasks", {
            "select": "id,agent_id,task_type,status,created_at,completed_at",
            "created_at": f"gte.{(now - timedelta(hours=24)).isoformat()}",
            "order": "created_at.desc",
            "limit": "50",
        }),
        # Last 5 ingestions
        _fetch("brain_raw_ingestions", {
            "select": "id,title,source_type,chunks_generated,status,created_at",
            "order": "created_at.desc",
            "limit": "5",
        }),
        # Active workflows
        _fetch("workflow_instances", {
            "select": "id,name,template_slug,status,current_step,created_at,updated_at",
            "status": "eq.running",
            "order": "created_at.desc",
            "limit": "10",
        }),
        # Active clients
        _fetch("clients", {
            "select": "id,name,company,mrr,status,has_zenya",
            "status": "eq.ativo",
            "order": "name.asc",
        }),
        # Counts via Supabase client (exact count)
        _count_table_since("brain_chunks", today_start),
        _count_table("brain_chunks"),
        _count_workflow_completed_today(today_start),
    )

    # Build agent status from running tasks + known agents
    known_agents = ["orion", "analyst", "dev", "qa", "architect", "po", "devops"]
    running_agent_ids = {t.get("agent_id", "").lower() for t in running_tasks}

    agents_status = []
    for agent_name in known_agents:
        is_working = agent_name in running_agent_ids
        # Find last task for this agent
        agent_tasks = [t for t in recent_tasks if (t.get("agent_id") or "").lower() == agent_name]
        last_action = None
        if agent_tasks:
            last = agent_tasks[0]
            last_action = {
                "task_type": last.get("task_type"),
                "status": last.get("status"),
                "at": last.get("created_at"),
            }
        agents_status.append({
            "id": agent_name,
            "status": "working" if is_working else "idle",
            "last_action": last_action,
        })

    # MRR total
    mrr_total = sum(c.get("mrr", 0) for c in active_clients)

    return {
        "agents": agents_status,
        "brain": {
            "chunks_today": chunks_today_count,
            "chunks_total": chunks_total_count,
            "last_ingestions": last_ingestions,
        },
        "workflows": {
            "active": active_workflows,
            "active_count": len(active_workflows),
            "completed_today": workflows_completed_today_count,
        },
        "clients": {
            "active": len(active_clients),
            "mrr_total": mrr_total,
            "list": active_clients,
        },
        "timestamp": now.isoformat(),
    }


async def _count_table_since(table: str, since_iso: str) -> int:
    """Count rows in a table since a given timestamp."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table(table)
            .select("id", count="exact")
            .gte("created_at", since_iso)
            .limit(1)
            .execute()
        )
        return res.count if res.count is not None else 0
    except Exception:
        return -1


async def _count_workflow_completed_today(today_start: str) -> int:
    """Count workflows completed today."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("workflow_instances")
            .select("id", count="exact")
            .eq("status", "completed")
            .gte("completed_at", today_start)
            .limit(1)
            .execute()
        )
        return res.count if res.count is not None else 0
    except Exception:
        return -1


@router.get("/crons")
async def get_crons(
    cron_name: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
):
    """
    Retorna log de execuções de crons com filtros opcionais.

    Query params:
        cron_name (opcional) — filtra por job_id (ex: health_check, brain_curate_02h)
        status    (opcional) — running | success | error
        since     (opcional) — ISO 8601 — filtra started_at >= since
        limit     (default 50, max 200)

    Response:
        {
          "total": N,
          "executions": [...],
          "summary": {
            "total_today": N,
            "errors_today": N,
            "running_now": N,
            "last_success_by_cron": {"cron_name": "iso_timestamp", ...}
          }
        }
    """
    effective_limit = min(max(1, limit), 200)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    async def _fetch_executions() -> list:
        try:
            q = (
                supabase.table("cron_executions")
                .select("id,cron_name,task_type,started_at,finished_at,duration_ms,status,error,rows_affected,task_id")
                .order("started_at", desc=True)
                .limit(effective_limit)
            )
            if cron_name:
                q = q.eq("cron_name", cron_name)
            if status:
                q = q.eq("status", status)
            if since:
                q = q.gte("started_at", since)
            res = await asyncio.to_thread(lambda: q.execute())
            return res.data or []
        except Exception as e:
            print(f"[system/crons] fetch executions failed: {e}")
            return []

    async def _fetch_today_stats() -> tuple[int, int, int]:
        """Retorna (total_today, errors_today, running_now)."""
        try:
            total_res, errors_res, running_res = await asyncio.gather(
                asyncio.to_thread(
                    lambda: supabase.table("cron_executions")
                    .select("id", count="exact")
                    .gte("started_at", today_start)
                    .limit(1)
                    .execute()
                ),
                asyncio.to_thread(
                    lambda: supabase.table("cron_executions")
                    .select("id", count="exact")
                    .eq("status", "error")
                    .gte("started_at", today_start)
                    .limit(1)
                    .execute()
                ),
                asyncio.to_thread(
                    lambda: supabase.table("cron_executions")
                    .select("id", count="exact")
                    .eq("status", "running")
                    .limit(1)
                    .execute()
                ),
            )
            total_today = total_res.count if total_res.count is not None else 0
            errors_today = errors_res.count if errors_res.count is not None else 0
            running_now = running_res.count if running_res.count is not None else 0
            return total_today, errors_today, running_now
        except Exception as e:
            print(f"[system/crons] fetch today stats failed: {e}")
            return 0, 0, 0

    async def _fetch_last_success() -> dict:
        """Retorna dict {cron_name: last_finished_at} para execuções de sucesso nas últimas 24h."""
        try:
            since_24h = (now - timedelta(hours=24)).isoformat()
            res = await asyncio.to_thread(
                lambda: supabase.table("cron_executions")
                .select("cron_name,finished_at")
                .eq("status", "success")
                .gte("started_at", since_24h)
                .order("started_at", desc=True)
                .limit(200)
                .execute()
            )
            rows = res.data or []
            last: dict[str, str] = {}
            for row in rows:
                name = row.get("cron_name", "")
                ts = row.get("finished_at") or ""
                if name and name not in last:
                    last[name] = ts
            return last
        except Exception as e:
            print(f"[system/crons] fetch last_success failed: {e}")
            return {}

    executions, (total_today, errors_today, running_now), last_success = await asyncio.gather(
        _fetch_executions(),
        _fetch_today_stats(),
        _fetch_last_success(),
    )

    return {
        "total": len(executions),
        "executions": executions,
        "summary": {
            "total_today": total_today,
            "errors_today": errors_today,
            "running_now": running_now,
            "last_success_by_cron": last_success,
        },
    }


@router.get("/state")
async def get_state(sprint_item: Optional[str] = None):
    """
    Consulta estado atual de sprint items.

    Query params:
        sprint_item (opcional) — filtra por item específico (ex: SPRINT8-P3)
    """
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_key
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase nao configurado")

    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    params: dict = {
        "order": "sprint_item.asc",
        "select": "sprint_item,title,status,verified,assigned_to,handoff_to,notes,updated_at",
    }
    if sprint_item:
        params["sprint_item"] = f"eq.{sprint_item}"
    else:
        params["sprint_item"] = "not.is.null"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supabase_url}/rest/v1/agent_work_items",
            params=params, headers=headers, timeout=10,
        )
        return resp.json()
