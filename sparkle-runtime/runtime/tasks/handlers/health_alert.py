"""
Verifica saúde das Zenyas ativas e alerta Mauro se algo estiver errado.
Roda a cada 15 minutos via ARQ cron.
Alertas enviados via WhatsApp para MAURO_WHATSAPP.

Checks realizados:
1. Agentes sem heartbeat por mais de 30 minutos
2. Tasks travadas em 'running' por mais de 10 minutos
3. Mais de 5 tasks 'failed' na última hora

Silêncio = saúde (sem alerta se tudo ok).
"""
from __future__ import annotations

from runtime.config import settings
from runtime.db import supabase


def handle_health_alert(task: dict) -> dict:
    """
    Verifica saúde do runtime e envia alertas via WhatsApp se necessário.
    Retorna {"message": "ok"} se tudo saudável, ou lista de alertas encontrados.
    """
    alerts: list[str] = []

    # 1. Agentes sem heartbeat por mais de 30 minutos
    try:
        res = supabase.rpc(
            "get_agents_stale_heartbeat",
            {"minutes_threshold": 30},
        ).execute()
        stale_agents = res.data or []
    except Exception:
        # Fallback: query direta se a RPC não existir
        try:
            res = supabase.table("agents").select("agent_id, last_heartbeat, status").execute()
            agents = res.data or []
            stale_agents = []
            for agent in agents:
                if not agent.get("last_heartbeat"):
                    continue
                from datetime import datetime, timezone, timedelta
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

    # 2. Tasks travadas em 'running' por mais de 10 minutos
    try:
        from datetime import datetime, timezone, timedelta
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
        details = ", ".join(
            f"{t.get('task_type', '?')} (agent={t.get('agent_id', '?')})"
            for t in stuck_tasks[:5]
        )
        alerts.append(f"🟡 *Tasks travadas em 'running' >10min:* {len(stuck_tasks)} — {details}")

    # 3. Tasks com muitas falhas recentes (>5 failed na última hora)
    try:
        from datetime import datetime, timezone, timedelta
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

    # Envia alerta se houver problemas
    if alerts:
        msg = "⚠️ *Alerta Sparkle Runtime*\n\n" + "\n".join(alerts)
        if settings.mauro_whatsapp:
            try:
                from runtime.integrations.zapi import send_text
                send_text(settings.mauro_whatsapp, msg)
                print(f"[health_alert] {len(alerts)} alerta(s) enviado(s) para {settings.mauro_whatsapp}")
            except Exception as e:
                print(f"[health_alert] falha ao enviar WhatsApp: {e}")
        else:
            print(f"[health_alert] MAURO_WHATSAPP não configurado — alerta não enviado:\n{msg}")
        return {"message": f"{len(alerts)} alerta(s) enviado(s)", "alerts": alerts}

    print("[health_alert] Todos os checks ok — sem alertas")
    return {"message": "ok", "alerts": []}
