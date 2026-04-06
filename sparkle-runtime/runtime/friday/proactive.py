"""
Friday Proactive Outreach — B3-02 (Lei 3: Friday doesn't wait to be called).

Friday reaches out to Mauro based on context, time, and events.
Anti-spam: max 1 message per trigger_type per day, quiet hours 22h-7h SP.
Global cap: max 5 proactive messages per day total.

Trigger types:
  - morning_checkin        : 8-9h  — pending items summary (incl. draft content count)
  - afternoon_nudge        : 14-15h — stuck tasks / items needing attention
  - eod_wrap               : 18-19h — day summary
  - milestone              : on significant events (brain growth, new client DNA, etc.)
  - anomaly_alert          : error rate spike or unusual system behaviour
  - idle_detection         : 4h+ without Mauro interaction during work hours
  - billing_blocked        : API billing/credit error detected in last 2h
  - content_failure_streak : 3+ consecutive generate_content failures
  - client_vencimento      : client payment due in next 3 days (fires at morning_checkin window)
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


async def _get_billing_blocked_tasks() -> list[dict]:
    """Tasks with billing/credit errors in the last 2h."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,task_type,status,result,created_at")
            .eq("status", "failed")
            .gte("created_at", cutoff)
            .execute()
        )
        tasks = res.data or []
        billing_keywords = ("billing", "credit", "quota", "insufficient_quota",
                            "payment", "saldo")
        blocked = []
        for t in tasks:
            result_str = str(t.get("result") or "").lower()
            if any(kw in result_str for kw in billing_keywords):
                blocked.append(t)
        return blocked
    except Exception as e:
        logger.error("proactive: _get_billing_blocked_tasks failed: %s", e)
        return []


async def _get_content_failure_streak() -> int:
    """
    Count consecutive generate_content failures (latest N tasks of that type).
    Returns streak count — stops counting when a 'done' is found.
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,status")
            .eq("task_type", "generate_content")
            .in_("status", ["failed", "done", "running", "pending"])
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        tasks = res.data or []
        streak = 0
        for t in tasks:
            status = t.get("status")
            if status in ("running", "pending"):
                return 0  # streak indeterminado — não alertar enquanto algo está em execução
            if status == "failed":
                streak += 1
            else:  # done
                break
        return streak
    except Exception as e:
        logger.error("proactive: _get_content_failure_streak failed: %s", e)
        return 0


async def _get_clients_due_soon(days_ahead: int = 3) -> list[dict]:
    """Clients with payment due (due_day) within the next `days_ahead` days."""
    try:
        now = _now_sp()
        upcoming_days = [(now + timedelta(days=d)).day for d in range(1, days_ahead + 1)]
        res = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,company,due_day,mrr")
            .eq("status", "active")
            .in_("due_day", upcoming_days)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("proactive: _get_clients_due_soon failed: %s", e)
        return []


async def _get_draft_content_count() -> int:
    """Count generated_content records with status='draft'."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("generated_content")
            .select("id", count="exact")
            .eq("status", "draft")
            .execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        logger.error("proactive: _get_draft_content_count failed: %s", e)
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
    """Morning check-in: summary of what's pending (incl. draft content count)."""
    now = _now_sp()
    if not (8 <= now.hour < 9):
        return None

    pending, drafts = await asyncio.gather(
        _get_pending_tasks(),
        _get_draft_content_count(),
    )
    completed_yesterday = await _get_completed_today()  # will be 0 early morning, that's fine

    if not pending and completed_yesterday == 0 and drafts == 0:
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

    if drafts > 0:
        parts.append(f"{drafts} conteudo(s) aguardando review.")

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


async def _eval_billing_blocked() -> str | None:
    """Alert when API billing/credit errors blocked tasks in the last 2h."""
    blocked = await _get_billing_blocked_tasks()
    if not blocked:
        return None
    task_types = list({t.get("task_type", "unknown") for t in blocked})
    types_str = ", ".join(task_types[:4])
    return (
        f"Alerta: {len(blocked)} task(s) falharam com erro de saldo/billing nas ultimas 2h "
        f"({types_str}). Verifique o credito da API — pode ter coisa parada esperando."
    )


async def _eval_content_failure_streak() -> str | None:
    """Alert when 3+ consecutive generate_content tasks have failed."""
    streak = await _get_content_failure_streak()
    if streak < 3:
        return None
    return (
        f"Atenção: {streak} gerações de conteudo falharam em sequencia (sem nenhum sucesso entre elas). "
        f"Vale investigar o handler de generate_content."
    )


async def _get_recently_closed_leads() -> list[dict]:
    """
    Leads com status='fechado' nas últimas 2h que ainda não foram notificados.
    Usamos o campo notes para marcar 'fechamento_notificado' e evitar re-envio.
    """
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        res = await asyncio.to_thread(
            lambda: supabase.table("leads")
            .select("id, name, phone, proposal_value, closed_at, notes")
            .eq("status", "fechado")
            .gte("closed_at", cutoff)
            .execute()
        )
        leads = res.data or []
        # Filtrar os que ainda NÃO foram notificados
        not_notified = []
        for lead in leads:
            notes = lead.get("notes") or ""
            if "fechamento_notificado" not in str(notes):
                not_notified.append(lead)
        return not_notified
    except Exception as e:
        logger.error("proactive: _get_recently_closed_leads failed: %s", e)
        return []


async def _mark_lead_notified(lead_id: str) -> None:
    """Marca o lead como notificado adicionando flag em notes."""
    try:
        # Busca notes atual
        res = await asyncio.to_thread(
            lambda: supabase.table("leads")
            .select("notes")
            .eq("id", lead_id)
            .single()
            .execute()
        )
        current_notes = (res.data or {}).get("notes") or ""
        flag = f" [fechamento_notificado:{datetime.now(timezone.utc).isoformat()[:10]}]"
        new_notes = (current_notes + flag).strip()
        await asyncio.to_thread(
            lambda: supabase.table("leads")
            .update({"notes": new_notes})
            .eq("id", lead_id)
            .execute()
        )
    except Exception as e:
        logger.error("proactive: _mark_lead_notified failed for %s: %s", lead_id, e)


async def _eval_lead_fechado() -> str | None:
    """
    FR15: Notifica Mauro quando um lead fecha.
    Verifica leads com status='fechado' nas últimas 2h ainda não notificados.
    Marca como notificado para evitar re-envio.
    """
    leads = await _get_recently_closed_leads()
    if not leads:
        return None

    # Notificar o primeiro (caso haja múltiplos, cada um dispara o trigger
    # individualmente no próximo ciclo — evita mensagem gigante)
    lead = leads[0]
    name = lead.get("name") or "Lead"
    val = lead.get("proposal_value")
    val_str = f"R${val:.0f}/mês" if isinstance(val, (int, float)) else (f"R${val}" if val else "valor não registrado")

    # Marcar como notificado antes de enviar (fail-safe: melhor não notificar do que notificar duas vezes)
    lead_id = lead.get("id")
    if lead_id:
        await _mark_lead_notified(lead_id)

    return (
        f"Fechou! {name} entrou como cliente ({val_str}). "
        f"Hora de iniciar o onboarding — quer que eu acione o checklist?"
    )


async def _eval_client_vencimento() -> str | None:
    """Alert at morning window when a client has payment due in the next 3 days."""
    now = _now_sp()
    if not (8 <= now.hour < 9):
        return None

    due_soon = await _get_clients_due_soon(days_ahead=3)
    if not due_soon:
        return None

    lines = []
    for c in due_soon:
        label = c.get("company") or c.get("name", "?")
        due_day = c.get("due_day", "?")
        mrr = c.get("mrr")
        mrr_str = f" (R${mrr:.0f})" if mrr else ""
        lines.append(f"  - {label}: vencimento dia {due_day}{mrr_str}")

    clients_str = "\n".join(lines)
    return (
        f"Lembrete: {len(due_soon)} cliente(s) com vencimento nos proximos 3 dias:\n{clients_str}"
    )


# ── Main check ───────────────────────────────────────────────

_TRIGGER_EVALUATORS: list[tuple[str, callable]] = [
    ("morning_checkin", _eval_morning_checkin),
    ("afternoon_nudge", _eval_afternoon_nudge),
    ("eod_wrap", _eval_eod_wrap),
    ("milestone", _eval_milestone),
    ("anomaly_alert", _eval_anomaly_alert),
    ("idle_detection", _eval_idle_detection),
    ("billing_blocked", _eval_billing_blocked),
    ("content_failure_streak", _eval_content_failure_streak),
    ("client_vencimento", _eval_client_vencimento),
    ("lead_fechado", _eval_lead_fechado),
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
