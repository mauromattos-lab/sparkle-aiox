"""
Task worker — ARQ-based async worker + in-process polling fallback.

Two modes:
1. ARQ worker (production): run `arq runtime.tasks.worker.WorkerSettings`
2. In-process polling (development / when Redis isn't available):
   the /tasks/poll endpoint processes one pending task synchronously.

Both update runtime_tasks status in Supabase.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from arq import cron
from arq.connections import RedisSettings

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.registry import get_handler

router = APIRouter()


# ── Core executor ──────────────────────────────────────────

async def execute_task(task: dict) -> None:
    """
    Execute a single task asynchronously.
    Updates Supabase status: running → done | failed.
    """
    task_id = task["id"]
    task_type = task.get("task_type", "")

    await _update_task(task_id, {"status": "running", "started_at": _now()})

    handler = get_handler(task_type)
    if not handler:
        await _update_task(task_id, {
            "status": "failed",
            "error": f"No handler registered for task_type '{task_type}'",
            "completed_at": _now(),
        })
        return

    try:
        result = await handler(task)
        await _update_task(task_id, {
            "status": "done",
            "result": result,
            "completed_at": _now(),
        })
    except Exception as e:
        retry_count = task.get("retry_count", 0)
        max_retries = task.get("max_retries", 3)
        if retry_count < max_retries:
            await _update_task(task_id, {
                "status": "pending",
                "retry_count": retry_count + 1,
                "error": str(e),
            })
        else:
            await _update_task(task_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": _now(),
            })


async def _update_task(task_id: str, data: dict) -> None:
    data["updated_at"] = _now()
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").update(data).eq("id", task_id).execute()
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── In-process polling endpoint (dev / no-Redis fallback) ──

@router.post("/poll")
async def poll_one_task():
    """
    Pick the highest-priority pending task and execute it.
    Used in development or as fallback when ARQ worker isn't running.
    """
    res = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("*")
        .eq("status", "pending")
        .order("priority", desc=True)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )
    if not res.data:
        return {"status": "no_tasks"}

    task = res.data[0]
    await execute_task(task)
    return {"status": "executed", "task_id": task["id"], "task_type": task["task_type"]}


# ── ARQ worker settings ─────────────────────────────────────

async def process_pending_tasks(ctx: dict) -> None:
    """ARQ job: poll and process all pending tasks in parallel."""
    res = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("*")
        .eq("status", "pending")
        .order("priority", desc=True)
        .order("created_at", desc=False)
        .limit(20)
        .execute()
    )
    tasks = res.data or []
    if tasks:
        await asyncio.gather(*[execute_task(task) for task in tasks])


async def trigger_daily_briefing(ctx: dict) -> None:
    """
    ARQ cron: dispara a task daily_briefing às 8h de Brasília (11h UTC).
    Insere uma task na fila para ser executada pelo process_pending_tasks.
    """
    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "daily_briefing",
            "payload": {"source": "cron_8h_brasilia"},
            "status": "pending",
            "priority": 8,
        }).execute()
    )
    task_id = task.data[0]["id"] if task.data else None
    print(f"[worker] daily_briefing triggered — task_id={task_id}")


async def trigger_health_check(ctx: dict) -> None:
    """
    ARQ cron: dispara a task health_alert a cada 15 minutos.
    Verifica saúde das Zenyas e alerta Mauro via WhatsApp se houver problema.
    """
    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "health_alert",
            "payload": {"source": "cron_15min"},
            "status": "pending",
            "priority": 8,
        }).execute()
    )
    task_id = task.data[0]["id"] if task.data else None
    print(f"[worker] health_alert triggered — task_id={task_id}")


class WorkerSettings:
    functions = [process_pending_tasks, trigger_daily_briefing, trigger_health_check]
    cron_jobs = [
        cron(process_pending_tasks, second={0, 15, 30, 45}),       # every 15 seconds
        cron(trigger_daily_briefing, hour={11}, minute={0}),        # 11h UTC = 8h Brasília
        cron(trigger_health_check, second={0}, minute={0, 15, 30, 45}),  # every 15 min
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 120
