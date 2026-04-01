"""
Scheduler interno — roda jobs agendados dentro do processo FastAPI.
Fallback quando ARQ worker (Redis) não está disponível.

Jobs:
- health_check : a cada 15 minutos
- daily_briefing: todo dia às 8h de Brasília (11h UTC)

Ambos criam a task no Supabase E executam inline via execute_task(),
fechando o loop sem depender do ARQ worker.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from runtime.db import supabase
from runtime.config import settings

_scheduler = AsyncIOScheduler()
_TZ = ZoneInfo("America/Sao_Paulo")


def _run_and_execute(task_type: str, priority: int = 5) -> None:
    """Cria task no Supabase e executa inline (modo dev sem ARQ)."""
    # Import aqui para evitar importação circular no module-level
    from runtime.tasks.worker import execute_task

    try:
        res = supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": task_type,
            "payload": {"triggered_by": "scheduler"},
            "status": "pending",
            "priority": priority,
        }).execute()

        if not res.data:
            print(f"[scheduler] WARN: insert para {task_type} não retornou dados")
            return

        task = res.data[0]
        print(f"[scheduler] Task {task_type} criada — id={task['id']}")
        execute_task(task)
        print(f"[scheduler] Task {task_type} executada")
    except Exception as e:
        print(f"[scheduler] Erro em {task_type}: {e}")


def _run_health_check() -> None:
    _run_and_execute("health_alert", priority=8)


def _run_daily_briefing() -> None:
    _run_and_execute("daily_briefing", priority=6)


def _run_weekly_briefing() -> None:
    _run_and_execute("weekly_briefing", priority=6)


def start_scheduler() -> None:
    """Inicia o scheduler — chamado no lifespan startup do FastAPI."""
    # Health check a cada 15 minutos
    _scheduler.add_job(
        _run_health_check,
        trigger=IntervalTrigger(minutes=15),
        id="health_check",
        replace_existing=True,
    )

    # Daily briefing às 8h de Brasília (11h UTC)
    _scheduler.add_job(
        _run_daily_briefing,
        trigger=CronTrigger(hour=8, minute=0, timezone=_TZ),
        id="daily_briefing",
        replace_existing=True,
    )

    # Weekly briefing todo domingo às 8h de Brasília (11h UTC)
    _scheduler.add_job(
        _run_weekly_briefing,
        trigger=CronTrigger(day_of_week="sun", hour=8, minute=0, timezone=_TZ),
        id="weekly_briefing",
        replace_existing=True,
    )

    _scheduler.start()
    print("[scheduler] APScheduler iniciado — briefing 8h Brasília, weekly briefing dom 8h, health check 15min")


def stop_scheduler() -> None:
    """Para o scheduler — chamado no lifespan shutdown do FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown()
        print("[scheduler] APScheduler parado")
