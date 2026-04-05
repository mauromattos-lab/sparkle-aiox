"""
Scheduler interno — roda jobs agendados dentro do processo FastAPI.
Fallback quando ARQ worker (Redis) não está disponível.

Jobs (18 total):
- health_check              : a cada 15 minutos
- daily_briefing            : todo dia às 8h de Brasília
- cockpit_summary           : todo dia às 8h de Brasília (11h UTC) — TIER 1 executive view
- daily_decision_moment     : todo dia às 9h de Brasília (S9-P5)
- weekly_briefing           : todo domingo às 8h de Brasília
- observer_gap_analysis     : toda segunda às 8h de Brasília (SYS-5, substitui gap_report)
- billing_risk              : todo dia às 8h45 de Brasília (OPS-4)
- risk_alert                : todo dia às 9h30 de Brasília (OPS-4)
- upsell_opportunity        : toda segunda às 7h30 de Brasília (OPS-4)
- brain_weekly_digest       : todo domingo às 23h de Brasília (SYS-1.6)
- content_weekly_batch      : toda segunda às 7h de Brasília (F2-P1)
- friday_proactive_check    : a cada 30 min das 7h às 21h30 de Brasília (B3-02)
- brain_archival            : todo dia às 3h de Brasília (B3-05)
- brain_curate              : 3x/dia às 2h, 10h, 18h UTC (S8-P1 auto-curation, Gap-1)
- client_dna_refresh        : toda segunda às 4h de Brasília (SYS-4, after curation)
- client_reports_monthly    : dia 1 de cada mês às 10h UTC (7h BRT)
- onboarding_check_gates    : a cada hora (ONB-1: verifica gates de onboarding em progresso)
- post_golive_health_check  : 2x/dia 08h e 20h BRT (ONB-1.9: health check pos-go-live)

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
from runtime.cron_logger import log_cron

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


@log_cron("health_check")
async def _run_health_check() -> None:
    await _run_and_execute("health_alert", priority=8)


@log_cron("daily_briefing")
async def _run_daily_briefing() -> None:
    await _run_and_execute("daily_briefing", priority=6)


@log_cron("cockpit_summary")
async def _run_cockpit_summary() -> None:
    await _run_and_execute("cockpit_summary", priority=7)


@log_cron("weekly_briefing")
async def _run_weekly_briefing() -> None:
    await _run_and_execute("weekly_briefing", priority=6)


async def _run_gap_report() -> None:
    await _run_and_execute("gap_report", priority=7)


@log_cron("observer_gap_analysis")
async def _run_observer_gap_analysis() -> None:
    await _run_and_execute("observer_gap_analysis", priority=7)


@log_cron("daily_decision_moment")
async def _run_daily_decision_moment() -> None:
    await _run_and_execute("daily_decision_moment", priority=9)


# ── OPS-4: Friday proactive initiatives ─────────────────────

@log_cron("billing_risk")
async def _run_billing_risk() -> None:
    await _run_and_execute("friday_initiative_billing", priority=7)


@log_cron("risk_alert")
async def _run_risk_alert() -> None:
    await _run_and_execute("friday_initiative_risk", priority=7)


@log_cron("upsell_opportunity")
async def _run_upsell_opportunity() -> None:
    await _run_and_execute("friday_initiative_upsell", priority=5)


# ── B3-05: Brain Archival (daily) ──────────────────────────

@log_cron("brain_archival")
async def _run_brain_archival() -> None:
    await _run_and_execute("brain_archival", priority=4)


# ── S8-P1: Brain Auto-Curation (daily) ─────────────────────
# NOTA: _run_brain_curate NÃO recebe @log_cron aqui pois é registrada com 3 job_ids
# distintos (brain_curate_02h, brain_curate_10h, brain_curate_18h).
# O decorator é aplicado inline no add_job — ver start_scheduler().

async def _run_brain_curate() -> None:
    await _run_and_execute("brain_curate", priority=4)


# ── SYS-4: Client DNA Refresh (weekly) ─────────────────────

@log_cron("client_dna_refresh")
async def _run_client_dna_refresh() -> None:
    await _run_and_execute("extract_all_client_dna", priority=4)


# ── Monthly Client Reports ───────────────────────────────────

@log_cron("client_reports_monthly")
async def _run_client_reports_monthly() -> None:
    await _run_and_execute("client_reports_bulk", priority=6)


# ── SYS-1.6: Brain Weekly Digest ────────────────────────────

@log_cron("brain_weekly_digest")
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

@log_cron("content_weekly_batch")
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


# ── ONB-1: Onboarding Gate Check (hourly) ──────────────────

@log_cron("onboarding_check_gates")
async def _run_onboarding_check_gates() -> None:
    """
    ONB-1 AC-4.1/4.2/4.3/4.4: Verifica gates de onboarding em progresso a cada hora.
    Avanca fases automaticamente quando gates sao satisfeitos.
    Alerta Friday se fase > 72h sem progresso.
    """
    import asyncio
    from runtime.onboarding.service import run_onboarding_gate_check

    try:
        result = await run_onboarding_gate_check()
        print(
            f"[scheduler] onboarding_check_gates: checked={result.get('checked', 0)}, "
            f"advanced={result.get('advanced', 0)}, alerts={result.get('alerts_sent', 0)}, "
            f"stale={result.get('stale_marked', 0)}"
        )
    except Exception as e:
        print(f"[scheduler] onboarding_check_gates: erro — {e}")


# ── ONB-1.9: Post Go-Live Health Check (2x/dia) ─────────────

@log_cron("post_golive_health_check")
async def _run_post_golive_health_check() -> None:
    """
    ONB-1.9: Health check pos-go-live — roda 2x por dia (08h e 20h BRT).
    Verifica volume, escalacao e sentiment de clientes em post_go_live.
    Gera relatorio de 1a semana e marca onboarding como completed apos 30 dias.
    """
    await _run_and_execute("post_golive_health", priority=5)


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

    # B3-05: brain_archival todo dia às 3h de Brasília (off-peak)
    _scheduler.add_job(
        _run_brain_archival,
        trigger=CronTrigger(hour=3, minute=0, timezone=_TZ),
        id="brain_archival",
        replace_existing=True,
    )

    # S8-P1 / Gap-1: brain_curate 3x/dia às 2h, 10h, 18h UTC
    # (batch=50, parallel=5 — drains 150 chunks/day instead of 20)
    # Decorator aplicado inline para preservar cron_name distinto por job_id
    _scheduler.add_job(
        log_cron("brain_curate_02h")(_run_brain_curate),
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="brain_curate_02h",
        replace_existing=True,
    )
    _scheduler.add_job(
        log_cron("brain_curate_10h")(_run_brain_curate),
        trigger=CronTrigger(hour=10, minute=0, timezone="UTC"),
        id="brain_curate_10h",
        replace_existing=True,
    )
    _scheduler.add_job(
        log_cron("brain_curate_18h")(_run_brain_curate),
        trigger=CronTrigger(hour=18, minute=0, timezone="UTC"),
        id="brain_curate_18h",
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

    # SYS-4: client DNA refresh toda segunda às 4h de Brasília (off-peak, after curation)
    _scheduler.add_job(
        _run_client_dna_refresh,
        trigger=CronTrigger(day_of_week="mon", hour=4, minute=0, timezone=_TZ),
        id="client_dna_refresh",
        replace_existing=True,
    )

    # ONB-1: onboarding gate check a cada hora
    _scheduler.add_job(
        _run_onboarding_check_gates,
        trigger=IntervalTrigger(hours=1),
        id="onboarding_check_gates",
        replace_existing=True,
    )

    # ONB-1.9: post-go-live health check 2x/dia (08h e 20h BRT)
    _scheduler.add_job(
        _run_post_golive_health_check,
        trigger=CronTrigger(hour=8, minute=0, timezone=_TZ),
        id="post_golive_health_check_08h",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_post_golive_health_check,
        trigger=CronTrigger(hour=20, minute=0, timezone=_TZ),
        id="post_golive_health_check_20h",
        replace_existing=True,
    )

    # ── B2-02: Character Orchestrator periodic jobs ──────────
    from runtime.characters.scheduler import register_character_jobs
    register_character_jobs(_scheduler)

    # ── B3-02: Friday Proactive Outreach jobs ─────────────────
    from runtime.friday.proactive_scheduler import register_proactive_jobs
    register_proactive_jobs(_scheduler)

    _scheduler.start()
    jobs = _scheduler.get_jobs()
    job_names = ", ".join(j.id for j in jobs)
    print(f"[scheduler] APScheduler iniciado — {len(jobs)} jobs: {job_names}")


def stop_scheduler() -> None:
    """Para o scheduler — chamado no lifespan shutdown do FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown()
        print("[scheduler] APScheduler parado")
