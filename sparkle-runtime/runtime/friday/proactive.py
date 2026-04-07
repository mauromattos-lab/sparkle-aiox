# DESATIVADO — Wave 0. Redesign com triggers de negócio em W1-FRIDAY-1.
# Bugs identificados: canal Z-API errado (MAURO_WHATSAPP apontava para número da Zenya),
# duplicatas por múltiplas réplicas Coolify com APScheduler independentes,
# conteúdo técnico (runtime_tasks) em vez de gatilhos de negócio.
# Desativação via PROACTIVE_ENABLED=false (env var, default false em config.py).

"""
Friday Proactive Outreach — B3-02 (Lei 3: Friday doesn't wait to be called).

Friday reaches out to Mauro based on context, time, and events.
Anti-spam: max 1 message per trigger_type per day, quiet hours 22h-7h SP.
Global cap: max 5 proactive messages per day total.

Trigger types:
  - morning_checkin   : 8-9h  — pending items summary
  - afternoon_nudge   : 14-15h — stuck tasks / items needing attention
  - eod_wrap          : 18-19h — day summary
  - milestone         : on significant events (brain growth, new client DNA, etc.)
  - anomaly_alert     : error rate spike or unusual system behaviour
  - idle_detection    : 4h+ without Mauro interaction during work hours
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("America/Sao_Paulo")
_QUIET_START = 22  # 22h SP
_QUIET_END = 7     # 7h SP
_MAX_PER_DAY_TOTAL = 5


# ── Anti-spam ────────────────────────────────────────────────

def _now_sp() -> datetime:
    return datetime.now(_TZ)


async def should_send(trigger_type: str) -> bool:
    """
    Check whether a proactive message of this type can be sent now.
    Rules:
      1. Quiet hours (22h-7h SP) — never send
      2. Max 1 per trigger_type per calendar day (SP timezone)
      3. Max 5 proactive messages total per calendar day
    """
    now = _now_sp()

    # Rule 1: quiet hours
    if now.hour >= _QUIET_START or now.hour < _QUIET_END:
        logger.debug("proactive: quiet hours — skipping %s", trigger_type)
        return False

    # Calculate start of today in SP → UTC for DB query
    today_start_sp = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_sp.astimezone(timezone.utc).isoformat()

    try:
        # Rule 2: already sent this trigger_type today?
        res = await asyncio.to_thread(
            lambda: supabase.table("proactive_outreach_log")
            .select("id", count="exact")
            .eq("trigger_type", trigger_type)
            .gte("sent_at", today_start_utc)
            .execute()
        )
        type_count = res.count if res.count is not None else len(res.data or [])
        if type_count > 0:
            logger.debug("proactive: %s already sent today — skipping", trigger_type)
            return False

        # Rule 3: global daily cap
        res_all = await asyncio.to_thread(
            lambda: supabase.table("proactive_outreach_log")
            .select("id", count="exact")
            .gte("sent_at", today_start_utc)
            .execute()
        )
        total_count = res_all.count if res_all.count is not None else len(res_all.data or [])
        if total_count >= _MAX_PER_DAY_TOTAL:
            logger.debug("proactive: daily cap reached (%d/%d) — skipping %s",
                         total_count, _MAX_PER_DAY_TOTAL, trigger_type)
            return False

    except Exception as e:
        logger.error("proactive: should_send check failed: %s", e)
        return False  # fail closed — don't spam on error

    return True


async def send_proactive(message: str, trigger_type: str) -> dict:
    """
    Send a proactive message to Mauro via Z-API and log it.
    Returns the log record or error dict.
    """
    from runtime.integrations.zapi import send_text

    phone = settings.mauro_whatsapp
    if not phone:
        logger.warning("proactive: MAURO_WHATSAPP not configured — cannot send")
        return {"error": "MAURO_WHATSAPP not set"}

    try:
        await asyncio.to_thread(send_text, phone, message)
        logger.info("proactive: sent [%s] to %s — %s", trigger_type, phone, message[:80])
    except Exception as e:
        logger.error("proactive: Z-API send failed for [%s]: %s", trigger_type, e)
        return {"error": f"send failed: {e}"}

    # Log to DB
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("proactive_outreach_log").insert({
                "trigger_type": trigger_type,
                "message_preview": message[:200],
            }).execute()
        )
        return res.data[0] if res.data else {"status": "sent", "trigger_type": trigger_type}
    except Exception as e:
        logger.error("proactive: log insert failed for [%s]: %s", trigger_type, e)
        return {"status": "sent_but_not_logged", "trigger_type": trigger_type}


# ── Data gatherers ───────────────────────────────────────────

async def _get_pending_tasks() -> list[dict]:
    """Fetch pending/running tasks from the last 24h."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,task_type,status,created_at")
            .in_("status", ["pending", "running"])
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("proactive: _get_pending_tasks failed: %s", e)
        return []


async def _get_stuck_tasks() -> list[dict]:
    """Tasks in 'running' for more than 10 minutes."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,task_type,status,created_at")
            .eq("status", "running")
            .lte("created_at", cutoff)
            .limit(10)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("proactive: _get_stuck_tasks failed: %s", e)
        return []


async def _get_completed_today() -> int:
    """Count tasks completed today (SP timezone)."""
    try:
        now = _now_sp()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_utc = today_start.astimezone(timezone.utc).isoformat()
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id", count="exact")
            .eq("status", "done")
            .gte("created_at", today_utc)
            .execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        logger.error("proactive: _get_completed_today failed: %s", e)
        return 0


async def _get_failed_last_hour() -> int:
    """Count failed tasks in the last hour."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id", count="exact")
            .eq("status", "failed")
            .gte("created_at", cutoff)
            .execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        logger.error("proactive: _get_failed_last_hour failed: %s", e)
        return 0


async def _get_brain_chunk_count() -> int:
    """Total brain_chunks count."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id", count="exact")
            .execute()
        )
        return res.count if res.count is not None else 0
    except Exception as e:
        logger.error("proactive: _get_brain_chunk_count failed: %s", e)
        return 0


async def _get_last_mauro_interaction() -> datetime | None:
    """Timestamp of Mauro's last message to Friday."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("created_at")
            .eq("agent_id", "friday")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows and rows[0].get("created_at"):
            ts = rows[0]["created_at"]
            # Parse ISO format — Supabase returns UTC
            if isinstance(ts, str):
                # Handle both Z and +00:00 suffixes
                ts = ts.replace("Z", "+00:00")
                return datetime.fromisoformat(ts)
        return None
    except Exception as e:
        logger.error("proactive: _get_last_mauro_interaction failed: %s", e)
        return None


# ── Trigger evaluators ───────────────────────────────────────

async def _eval_morning_checkin() -> str | None:
    """Morning check-in: summary of what's pending."""
    now = _now_sp()
    if not (8 <= now.hour < 9):
        return None

    pending = await _get_pending_tasks()
    completed_yesterday = await _get_completed_today()  # will be 0 early morning, that's fine

    if not pending and completed_yesterday == 0:
        return "Bom dia! Tudo limpo por aqui, sem tasks pendentes. Dia tranquilo pra frente."

    parts = ["Bom dia!"]
    if pending:
        types = {}
        for t in pending:
            tt = t.get("task_type", "unknown")
            types[tt] = types.get(tt, 0) + 1
        summary = ", ".join(f"{v}x {k}" for k, v in list(types.items())[:4])
        parts.append(f"{len(pending)} tasks pendentes ({summary}).")
    else:
        parts.append("Nenhuma task pendente.")

    return " ".join(parts)


async def _eval_afternoon_nudge() -> str | None:
    """Afternoon nudge: stuck tasks or items needing attention."""
    now = _now_sp()
    if not (14 <= now.hour < 15):
        return None

    stuck = await _get_stuck_tasks()
    failed = await _get_failed_last_hour()

    if not stuck and failed == 0:
        return None  # nothing to nudge about

    parts = []
    if stuck:
        task_types = [t.get("task_type", "?") for t in stuck[:3]]
        parts.append(f"{len(stuck)} task(s) travada(s): {', '.join(task_types)}.")
    if failed > 0:
        parts.append(f"{failed} falha(s) na ultima hora.")

    if parts:
        return "Oi! Notei algo que precisa de atenção. " + " ".join(parts)
    return None


async def _eval_eod_wrap() -> str | None:
    """End-of-day wrap: day summary."""
    now = _now_sp()
    if not (18 <= now.hour < 19):
        return None

    completed = await _get_completed_today()
    pending = await _get_pending_tasks()
    failed = await _get_failed_last_hour()

    parts = ["Resumo do dia:"]
    parts.append(f"{completed} tasks completas.")
    if pending:
        parts.append(f"{len(pending)} pendentes.")
    if failed > 0:
        parts.append(f"{failed} com falha.")
    if completed == 0 and not pending and failed == 0:
        return None  # quiet day, no wrap needed

    return " ".join(parts)


async def _eval_milestone() -> str | None:
    """Celebrate significant milestones (brain growth, etc.)."""
    chunk_count = await _get_brain_chunk_count()
    if chunk_count <= 0:
        return None

    # Celebrate at round numbers: 100, 250, 500, 1000, 2500, 5000
    milestones = [100, 250, 500, 1000, 2500, 5000]
    for m in milestones:
        if chunk_count >= m and chunk_count < m + 5:
            # Check if we already celebrated this milestone
            return f"Marco! O Brain atingiu {chunk_count} chunks de conhecimento. A base de inteligencia ta crescendo."

    return None


async def _eval_anomaly_alert() -> str | None:
    """Alert on error rate spikes."""
    failed = await _get_failed_last_hour()
    if failed >= 5:
        return f"Alerta: {failed} tasks falharam na ultima hora. Pode ser algo no sistema que precisa de atenção."
    return None


async def _eval_idle_detection() -> str | None:
    """Gentle check-in if Mauro hasn't interacted in 4+ hours during work hours."""
    now = _now_sp()
    # Only during work hours (9h-18h)
    if not (9 <= now.hour < 18):
        return None

    last = await _get_last_mauro_interaction()
    if last is None:
        return None

    # Ensure last is timezone-aware
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    hours_since = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    if hours_since >= 4:
        return "Faz um tempo que a gente nao se fala. Tudo certo por ai? Se precisar de algo, to aqui."
    return None


# ── Main check ───────────────────────────────────────────────

_TRIGGER_EVALUATORS: list[tuple[str, callable]] = [
    ("morning_checkin", _eval_morning_checkin),
    ("afternoon_nudge", _eval_afternoon_nudge),
    ("eod_wrap", _eval_eod_wrap),
    ("milestone", _eval_milestone),
    ("anomaly_alert", _eval_anomaly_alert),
    ("idle_detection", _eval_idle_detection),
]


async def check_proactive_triggers() -> list[dict]:
    """
    Evaluate all trigger conditions. For each that fires AND passes
    anti-spam, send the message.

    Returns list of results (sent messages or skipped reasons).
    """
    results = []

    for trigger_type, evaluator in _TRIGGER_EVALUATORS:
        try:
            message = await evaluator()
            if message is None:
                continue

            can_send = await should_send(trigger_type)
            if not can_send:
                results.append({
                    "trigger_type": trigger_type,
                    "status": "skipped_anti_spam",
                })
                continue

            result = await send_proactive(message, trigger_type)
            results.append({
                "trigger_type": trigger_type,
                "status": "sent",
                "message_preview": message[:100],
                **result,
            })

        except Exception as e:
            logger.error("proactive: evaluator %s failed: %s", trigger_type, e)
            results.append({
                "trigger_type": trigger_type,
                "status": "error",
                "error": str(e)[:200],
            })

    if results:
        sent = [r for r in results if r.get("status") == "sent"]
        logger.info("proactive: check complete — %d evaluated, %d sent",
                     len(results), len(sent))
    return results
