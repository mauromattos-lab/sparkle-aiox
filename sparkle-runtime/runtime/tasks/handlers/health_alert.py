"""
Verifica saúde das Zenyas ativas e alerta Mauro se algo estiver errado.
Roda a cada 15 minutos via ARQ cron.
Alertas enviados via WhatsApp para MAURO_WHATSAPP.

Checks realizados:
1. Agentes sem heartbeat por mais de 30 minutos
2. Tasks travadas em 'running' por mais de 10 minutos — AUTO-RESOLVE para 'failed'
3. Mais de 5 tasks 'failed' na última hora

Anti-spam: não envia o mesmo alerta se já enviou nos últimos 60 min.
Silêncio = saúde (sem alerta se tudo ok).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from runtime.config import settings
from runtime.db import supabase

# Anti-spam: guarda hash do ultimo alerta + timestamp
_last_alert_hash: str = ""
_last_alert_time: datetime | None = None
_ANTI_SPAM_MINUTES = 60

# Consecutive failure tracking — alerta Mauro se health check falha 3x seguidas
_consecutive_failures: int = 0
_FAILURE_THRESHOLD = 3


async def handle_health_alert(task: dict) -> dict:
    """
    Verifica saúde do runtime e envia alertas via WhatsApp se necessário.
    Auto-resolve tasks travadas. Anti-spam de 60 min para alertas repetidos.
    """
    global _last_alert_hash, _last_alert_time, _consecutive_failures

    alerts: list[str] = []

    # 1. Agentes sem heartbeat por mais de 30 minutos
    try:
        res = supabase.rpc(
            "get_agents_stale_heartbeat",
            {"minutes_threshold": 30},
        ).execute()
        stale_agents = res.data or []
    except Exception:
        try:
            res = supabase.table("agents").select("agent_id, last_heartbeat, status").execute()
            agents = res.data or []
            stale_agents = []
            for agent in agents:
                if not agent.get("last_heartbeat"):
                    continue
                last = datetime.fromisoformat(agent["last_heartbeat"].replace("Z", "+00:00"))
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
                if last < cutoff:
                    stale_agents.append(agent)
        except Exception as e:
            stale_agents = []
            print(f"[health_alert] heartbeat check failed: {e}")

    if stale_agents:
        names = ", ".join(a.get("agent_id", "?") for a in stale_agents)
        alerts.append(f"🔴 *Agente(s) sem heartbeat >30min:* {names}")

    # 2. Tasks travadas em 'running' por mais de 10 minutos — AUTO-RESOLVE
    stuck_resolved = 0
    try:
        cutoff_running = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        res = (
            supabase.table("runtime_tasks")
            .select("id, task_type, agent_id, started_at")
            .eq("status", "running")
            .lt("started_at", cutoff_running)
            .execute()
        )
        stuck_tasks = res.data or []
    except Exception as e:
        stuck_tasks = []
        print(f"[health_alert] stuck tasks check failed: {e}")

    if stuck_tasks:
        # Auto-resolve: marcar como failed em vez de só alertar
        for t in stuck_tasks:
            try:
                supabase.table("runtime_tasks").update({
                    "status": "failed",
                    "result": {"error": "Auto-resolved: task travada >10min pelo health_alert"},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", t["id"]).execute()
                stuck_resolved += 1
            except Exception as e:
                print(f"[health_alert] falha ao auto-resolver task {t['id']}: {e}")

        details = ", ".join(
            f"{t.get('task_type', '?')} (agent={t.get('agent_id', '?')})"
            for t in stuck_tasks[:5]
        )
        alerts.append(
            f"🟡 *{len(stuck_tasks)} task(s) travada(s) — auto-resolvidas:* {details}"
        )

    # 3. Tasks com muitas falhas recentes (>5 failed na última hora)
    try:
        cutoff_failures = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        res = (
            supabase.table("runtime_tasks")
            .select("id, task_type")
            .eq("status", "failed")
            .gte("completed_at", cutoff_failures)
            .execute()
        )
        recent_failures = res.data or []
    except Exception as e:
        recent_failures = []
        print(f"[health_alert] failure count check failed: {e}")

    if len(recent_failures) > 5:
        by_type: dict[str, int] = {}
        for t in recent_failures:
            tt = t.get("task_type", "unknown")
            by_type[tt] = by_type.get(tt, 0) + 1
        top = sorted(by_type.items(), key=lambda x: -x[1])[:3]
        top_str = ", ".join(f"{tt}:{n}" for tt, n in top)
        alerts.append(f"🔴 *{len(recent_failures)} falhas na última hora:* {top_str}")

    # Track consecutive failures — escalate on 3x in a row
    if alerts:
        _consecutive_failures += 1
        if _consecutive_failures >= _FAILURE_THRESHOLD:
            alerts.insert(0, f"🚨 *ALERTA CRÍTICO:* health check falhou {_consecutive_failures}x consecutivas!")
    else:
        _consecutive_failures = 0

    # Envia alerta se houver problemas (com anti-spam)
    if alerts:
        alert_hash = "|".join(sorted(alerts))
        now = datetime.now(timezone.utc)

        # Anti-spam: não envia se o mesmo alerta foi enviado nos últimos 60 min
        is_duplicate = (
            alert_hash == _last_alert_hash
            and _last_alert_time is not None
            and (now - _last_alert_time) < timedelta(minutes=_ANTI_SPAM_MINUTES)
        )

        if is_duplicate:
            print(f"[health_alert] {len(alerts)} alerta(s) suprimido(s) — anti-spam (mesmo alerta <{_ANTI_SPAM_MINUTES}min)")
            return {
                "message": f"{len(alerts)} alerta(s) suprimido(s) pelo anti-spam",
                "alerts": alerts,
                "stuck_resolved": stuck_resolved,
                "suppressed": True,
            }

        msg = "⚠️ *Alerta Sparkle Runtime*\n\n" + "\n".join(alerts)
        if settings.mauro_whatsapp:
            try:
                from runtime.integrations.zapi import send_text
                send_text(settings.mauro_whatsapp, msg)
                _last_alert_hash = alert_hash
                _last_alert_time = now
                print(f"[health_alert] {len(alerts)} alerta(s) enviado(s) para {settings.mauro_whatsapp}")
            except Exception as e:
                print(f"[health_alert] falha ao enviar WhatsApp: {e}")
        else:
            print(f"[health_alert] MAURO_WHATSAPP não configurado — alerta não enviado:\n{msg}")
        return {"message": f"{len(alerts)} alerta(s) enviado(s)", "alerts": alerts, "stuck_resolved": stuck_resolved}

    print("[health_alert] Todos os checks ok — sem alertas")
    return {"message": "ok", "alerts": [], "stuck_resolved": stuck_resolved}
