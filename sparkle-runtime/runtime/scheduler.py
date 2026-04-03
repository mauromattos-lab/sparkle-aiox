"""
Scheduler interno — roda jobs agendados dentro do processo FastAPI.
Fallback quando ARQ worker (Redis) não está disponível.

Jobs (8 total):
- health_check            : a cada 15 minutos
- daily_briefing          : todo dia às 8h de Brasília
- daily_decision_moment   : todo dia às 9h de Brasília (S9-P5)
- weekly_briefing         : todo domingo às 8h de Brasília
- gap_report              : toda segunda às 8h de Brasília
- billing_risk            : todo dia às 8h45 de Brasília (OPS-4)
- risk_alert              : todo dia às 9h30 de Brasília (OPS-4)
- upsell_opportunity      : toda segunda às 7h30 de Brasília (OPS-4)

Todos criam a task no Supabase E executam inline via execute_task(),
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


async def _run_and_execute(task_type: str, priority: int = 5) -> None:
    """Cria task no Supabase e executa inline (modo dev sem ARQ)."""
    import asyncio
    # Import aqui para evitar importação circular no module-level
    from runtime.tasks.worker import execute_task

    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": task_type,
                "payload": {"triggered_by": "scheduler"},
                "status": "pending",
                "priority": priority,
            }).execute()
        )

        if not res.data:
            print(f"[scheduler] WARN: insert para {task_type} não retornou dados")
            return

        task = res.data[0]
        print(f"[scheduler] Task {task_type} criada — id={task['id']}")
        await execute_task(task)
        print(f"[scheduler] Task {task_type} executada")
    except Exception as e:
        print(f"[scheduler] Erro em {task_type}: {e}")


async def _run_health_check() -> None:
    await _run_and_execute("health_alert", priority=8)


async def _run_daily_briefing() -> None:
    await _run_and_execute("daily_briefing", priority=6)


async def _run_weekly_briefing() -> None:
    await _run_and_execute("weekly_briefing", priority=6)


async def _run_gap_report() -> None:
    await _run_and_execute("gap_report", priority=7)


async def _run_daily_decision_moment() -> None:
    await _run_and_execute("daily_decision_moment", priority=9)


# ── OPS-4: Friday proactive initiatives ─────────────────────

async def _run_billing_risk() -> None:
    await _run_and_execute("friday_initiative_billing", priority=7)


async def _run_risk_alert() -> None:
    await _run_and_execute("friday_initiative_risk", priority=7)


async def _run_upsell_opportunity() -> None:
    await _run_and_execute("friday_initiative_upsell", priority=5)


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

    # Gap report toda segunda-feira às 8h de Brasília (11h UTC)
    _scheduler.add_job(
        _run_gap_report,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=_TZ),
        id="gap_report",
        replace_existing=True,
    )

    # Daily Decision Moment às 9h de Brasília (12h UTC) — S9-P5
    _scheduler.add_job(
        _run_daily_decision_moment,
        trigger=CronTrigger(hour=9, minute=0, timezone=_TZ),
        id="daily_decision_moment",
        replace_existing=True,
    )

    # OPS-4: billing_risk às 8h45 de Brasília
    _scheduler.add_job(
        _run_billing_risk,
        trigger=CronTrigger(hour=8, minute=45, timezone=_TZ),
        id="billing_risk",
        replace_existing=True,
    )

    # OPS-4: risk_alert às 9h30 de Brasília
    _scheduler.add_job(
        _run_risk_alert,
        trigger=CronTrigger(hour=9, minute=30, timezone=_TZ),
        id="risk_alert",
        replace_existing=True,
    )

    # OPS-4: upsell_opportunity toda segunda às 7h30 de Brasília
    _scheduler.add_job(
        _run_upsell_opportunity,
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=_TZ),
        id="upsell_opportunity",
        replace_existing=True,
    )

    _scheduler.start()
    jobs = _scheduler.get_jobs()
    job_names = ", ".join(j.id for j in jobs)
    print(f"[scheduler] APScheduler iniciado — {len(jobs)} jobs: {job_names}")


def stop_scheduler() -> None:
    """Para o scheduler — chamado no lifespan shutdown do FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown()
        print("[scheduler] APScheduler parado")
