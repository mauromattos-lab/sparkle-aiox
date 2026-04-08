"""
Scheduler interno — roda jobs agendados dentro do processo FastAPI.
Fallback quando ARQ worker (Redis) não está disponível.

Jobs (15 total):
- health_check            : a cada 15 minutos
- daily_briefing          : todo dia às 8h de Brasília
- cockpit_summary         : todo dia às 8h de Brasília (11h UTC) — TIER 1 executive view
- daily_decision_moment   : todo dia às 9h de Brasília (S9-P5)
- weekly_briefing         : todo domingo às 8h de Brasília
- observer_gap_analysis   : toda segunda às 8h de Brasília (SYS-5, substitui gap_report)
- billing_risk            : todo dia às 8h45 de Brasília (OPS-4)
- risk_alert              : todo dia às 9h30 de Brasília (OPS-4)
- upsell_opportunity      : toda segunda às 7h30 de Brasília (OPS-4)
- brain_weekly_digest     : todo domingo às 23h de Brasília (SYS-1.6)
- content_weekly_batch    : toda segunda às 7h de Brasília (F2-P1)
- friday_proactive_check  : a cada 30 min das 7h às 21h30 de Brasília (B3-02)
- brain_archival          : todo dia às 3h de Brasília (B3-05)
- brain_curate            : todo dia às 2h UTC (S8-P1 auto-curation)
- client_reports_monthly  : dia 1 de cada mês às 10h UTC (7h BRT)
- client_health_weekly    : toda segunda às 9h de Brasília (W2-CLC-1)

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


async def _run_cockpit_summary() -> None:
    await _run_and_execute("cockpit_summary", priority=7)


async def _run_weekly_briefing() -> None:
    await _run_and_execute("weekly_briefing", priority=6)


async def _run_gap_report() -> None:
    await _run_and_execute("gap_report", priority=7)


async def _run_observer_gap_analysis() -> None:
    await _run_and_execute("observer_gap_analysis", priority=7)


async def _run_daily_decision_moment() -> None:
    await _run_and_execute("daily_decision_moment", priority=9)


# ── OPS-4: Friday proactive initiatives ─────────────────────

async def _run_billing_risk() -> None:
    await _run_and_execute("friday_initiative_billing", priority=7)


async def _run_risk_alert() -> None:
    await _run_and_execute("friday_initiative_risk", priority=7)


async def _run_upsell_opportunity() -> None:
    await _run_and_execute("friday_initiative_upsell", priority=5)


# ── W0-BRAIN-1: Brain Rejected Cleanup (daily) ─────────────

async def _run_brain_rejected_cleanup() -> None:
    """Soft-deleta chunks rejeitados >30 dias + dispara auto-curadoria para pending >7 dias."""
    from runtime.brain.curation import cleanup_rejected_chunks, trigger_autocurate_stale_pending
    await cleanup_rejected_chunks(days=30)
    await trigger_autocurate_stale_pending(days=7)


# ── B3-05: Brain Archival (daily) ──────────────────────────

async def _run_brain_archival() -> None:
    await _run_and_execute("brain_archival", priority=4)


# ── S8-P1: Brain Auto-Curation (daily) ─────────────────────

async def _run_brain_curate() -> None:
    await _run_and_execute("brain_curate", priority=4)


# ── Monthly Client Reports ───────────────────────────────────

async def _run_client_reports_monthly() -> None:
    await _run_and_execute("client_reports_bulk", priority=6)


# ── W2-CLC-1: Client Health Weekly Score ────────────────────

async def _run_client_health_weekly() -> None:
    """
    Recalcula Health Score de todos os clientes ativos.
    Roda toda segunda às 09h BRT. Usa calculator diretamente (sem task queue).
    """
    try:
        from runtime.client_health.calculator import calculate_all_health_scores
        results = await calculate_all_health_scores()
        healthy = sum(1 for r in results if r.get("classification") == "healthy")
        at_risk = sum(1 for r in results if r.get("classification") == "at_risk")
        critical = sum(1 for r in results if r.get("classification") == "critical")
        print(
            f"[scheduler] client_health_weekly: {len(results)} clientes — "
            f"{healthy} healthy, {at_risk} at_risk, {critical} critical"
        )
    except Exception as e:
        print(f"[scheduler] client_health_weekly: erro — {e}")


# ── SYS-1.6: Brain Weekly Digest ────────────────────────────

async def _run_brain_weekly_digest() -> None:
    """
    Busca conversas do Mauro com a Friday dos últimos 7 dias,
    agrupa por dia e dispara brain_ingest_pipeline para cada grupo.
    Se não encontrar conversas, loga e retorna sem erro.
    """
    import asyncio
    from datetime import datetime, timedelta, timezone
    from runtime.tasks.worker import execute_task

    try:
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        # Busca conversas recentes do Mauro com a Friday
        res = await asyncio.to_thread(
            lambda: supabase.table("conversation_history")
            .select("id,role,content,created_at")
            .gte("created_at", seven_days_ago)
            .order("created_at")
            .limit(500)
            .execute()
        )

        conversations = res.data or []
        if not conversations:
            print("[scheduler] brain_weekly_digest: nenhuma conversa nos últimos 7 dias — skip")
            return

        # Agrupa por dia (YYYY-MM-DD)
        by_day: dict[str, list[str]] = {}
        for conv in conversations:
            content = conv.get("content", "")
            if not content or len(content.strip()) < 10:
                continue
            day = (conv.get("created_at") or "")[:10]  # YYYY-MM-DD
            if day not in by_day:
                by_day[day] = []
            role = conv.get("role", "unknown")
            by_day[day].append(f"[{role}] {content}")

        if not by_day:
            print("[scheduler] brain_weekly_digest: conversas encontradas mas sem conteúdo relevante — skip")
            return

        print(f"[scheduler] brain_weekly_digest: {len(conversations)} conversas em {len(by_day)} dias — ingerindo")

        # Dispara brain_ingest_pipeline para o conteúdo agrupado
        all_content_parts = []
        for day in sorted(by_day.keys()):
            day_content = "\n".join(by_day[day])
            all_content_parts.append(f"=== {day} ===\n{day_content}")

        digest_text = "\n\n".join(all_content_parts)

        # Cria task brain_ingest_pipeline com o conteúdo consolidado
        task_res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "brain_ingest_pipeline",
                "payload": {
                    "triggered_by": "scheduler",
                    "raw_content": digest_text,
                    "title": f"weekly_digest_{sorted(by_day.keys())[0]}_to_{sorted(by_day.keys())[-1]}",
                    "source_type": "weekly_digest",
                    "persona": "mauro",
                    "run_dna": True,
                    "run_narrative": False,
                },
                "status": "pending",
                "priority": 4,
            }).execute()
        )

        if not task_res.data:
            print("[scheduler] brain_weekly_digest: falha ao criar task de ingestão")
            return

        task = task_res.data[0]
        print(f"[scheduler] brain_weekly_digest: task criada — id={task['id']}, ingerindo {len(digest_text)} chars")
        await execute_task(task)
        print(f"[scheduler] brain_weekly_digest: ingestão concluída")

    except Exception as e:
        print(f"[scheduler] brain_weekly_digest: erro — {e}")


# ── F2-P1: Content Weekly Batch ────────────────────────────

async def _run_content_weekly_batch() -> None:
    """
    Gera 5 posts variados para a semana, baseando-se nos domínios
    mais recentes do brain_insights para diversificar temas.
    """
    import asyncio
    from runtime.tasks.worker import execute_task

    try:
        # Busca domínios trending dos últimos 14 dias no brain_insights
        from datetime import datetime, timedelta, timezone

        fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

        res = await asyncio.to_thread(
            lambda: supabase.table("brain_insights")
            .select("domain, title")
            .gte("created_at", fourteen_days_ago)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )

        insights = res.data or []

        # Extrair domínios únicos, preservando ordem (mais recentes primeiro)
        seen: set[str] = set()
        domains: list[str] = []
        for ins in insights:
            d = ins.get("domain", "")
            if d and d not in seen:
                seen.add(d)
                domains.append(d)

        # Fallback: temas genéricos se não houver insights
        if len(domains) < 5:
            fallback = [
                "inteligência artificial para pequenos negócios",
                "automação de atendimento via WhatsApp",
                "marketing digital com IA",
                "produtividade para empreendedores",
                "tendências de tecnologia 2026",
            ]
            for fb in fallback:
                if fb not in seen:
                    domains.append(fb)
                    seen.add(fb)

        # Gerar 5 posts com temas variados
        formats = ["instagram_post", "carousel", "instagram_post", "carousel", "story"]
        personas = ["zenya", "mauro", "zenya", "finch", "zenya"]

        for i in range(5):
            topic = domains[i % len(domains)]
            fmt = formats[i]
            persona = personas[i]

            task_res = await asyncio.to_thread(
                lambda t=topic, f=fmt, p=persona: supabase.table("runtime_tasks").insert({
                    "agent_id": "content-engine",
                    "client_id": settings.sparkle_internal_client_id,
                    "task_type": "generate_content",
                    "payload": {
                        "triggered_by": "scheduler",
                        "topic": t,
                        "format": f,
                        "persona": p,
                        "source_type": "cron",
                    },
                    "status": "pending",
                    "priority": 4,
                }).execute()
            )

            if task_res.data:
                task = task_res.data[0]
                print(f"[scheduler] content_weekly_batch: post {i+1}/5 — {fmt}/{persona} topic='{topic[:40]}' — id={task['id']}")
                await execute_task(task)

        print("[scheduler] content_weekly_batch: 5 posts gerados para a semana")

    except Exception as e:
        print(f"[scheduler] content_weekly_batch: erro — {e}")


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

    # Cockpit Summary às 8h de Brasília (11h UTC) — TIER 1 executive view
    _scheduler.add_job(
        _run_cockpit_summary,
        trigger=CronTrigger(hour=11, minute=0, timezone="UTC"),
        id="cockpit_summary",
        replace_existing=True,
    )

    # Weekly briefing todo domingo às 8h de Brasília (11h UTC)
    _scheduler.add_job(
        _run_weekly_briefing,
        trigger=CronTrigger(day_of_week="sun", hour=8, minute=0, timezone=_TZ),
        id="weekly_briefing",
        replace_existing=True,
    )

    # Observer gap analysis toda segunda-feira às 8h de Brasília (substitui gap_report)
    _scheduler.add_job(
        _run_observer_gap_analysis,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=_TZ),
        id="observer_gap_analysis",
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

    # W0-BRAIN-1: brain_rejected_cleanup todo dia às 3h30 de Brasília (após archival)
    _scheduler.add_job(
        _run_brain_rejected_cleanup,
        trigger=CronTrigger(hour=3, minute=30, timezone=_TZ),
        id="brain_rejected_cleanup",
        replace_existing=True,
    )

    # B3-05: brain_archival todo dia às 3h de Brasília (off-peak)
    _scheduler.add_job(
        _run_brain_archival,
        trigger=CronTrigger(hour=3, minute=0, timezone=_TZ),
        id="brain_archival",
        replace_existing=True,
    )

    # S8-P1: brain_curate todo dia às 2h UTC (auto-curation via Haiku)
    _scheduler.add_job(
        _run_brain_curate,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="brain_curate",
        replace_existing=True,
    )

    # Monthly client reports: dia 1 de cada mês às 10h UTC (7h BRT)
    _scheduler.add_job(
        _run_client_reports_monthly,
        trigger=CronTrigger(day=1, hour=10, minute=0, timezone="UTC"),
        id="client_reports_monthly",
        replace_existing=True,
    )

    # SYS-1.6: brain_weekly_digest todo domingo às 23h de Brasília
    _scheduler.add_job(
        _run_brain_weekly_digest,
        trigger=CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=_TZ),
        id="brain_weekly_digest",
        replace_existing=True,
    )

    # F2-P1: content_weekly_batch toda segunda às 7h de Brasília
    _scheduler.add_job(
        _run_content_weekly_batch,
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=0, timezone=_TZ),
        id="content_weekly_batch",
        replace_existing=True,
    )

    # W2-CLC-1: client_health_weekly toda segunda às 9h de Brasília
    _scheduler.add_job(
        _run_client_health_weekly,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=_TZ),
        id="client_health_weekly",
        replace_existing=True,
    )

    # ── B2-02: Character Orchestrator periodic jobs ──────────
    from runtime.characters.scheduler import register_character_jobs
    register_character_jobs(_scheduler)

    # ── B3-02: Friday Proactive Outreach jobs ─────────────────
    from runtime.friday.proactive_scheduler import register_proactive_jobs
    register_proactive_jobs(_scheduler)

    # ── CONTENT-2.2: Content crons (pipeline_tick, publisher_tick, brain_sync, stuck_check) ──
    from runtime.crons.content import register_content_jobs
    register_content_jobs(_scheduler)

    # ── AIOS-E-02: AIOS gate monitor (daily 09h BRT) ─────────
    from runtime.aios.gate_monitor import register_aios_jobs
    register_aios_jobs(_scheduler)

    _scheduler.start()
    jobs = _scheduler.get_jobs()
    job_names = ", ".join(j.id for j in jobs)
    print(f"[scheduler] APScheduler iniciado — {len(jobs)} jobs: {job_names}")


def stop_scheduler() -> None:
    """Para o scheduler — chamado no lifespan shutdown do FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown()
        print("[scheduler] APScheduler parado")
