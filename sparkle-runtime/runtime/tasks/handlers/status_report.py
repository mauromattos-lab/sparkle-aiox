"""
Status report handler.
Friday asks: "como estão os clientes?" / "qual o MRR?"
This handler queries Supabase and returns a summary.
"""
from __future__ import annotations

from runtime.db import supabase


async def handle_status_report(task: dict) -> dict:
    summary_lines = []

    # Active agents
    agents_res = supabase.table("agents").select("agent_id, status, last_heartbeat").execute()
    agents = agents_res.data or []
    idle = [a["agent_id"] for a in agents if a["status"] == "idle"]
    running = [a["agent_id"] for a in agents if a["status"] == "running"]
    error = [a["agent_id"] for a in agents if a["status"] == "error"]

    summary_lines.append(f"Agentes ativos: {len(agents)}")
    if running:
        summary_lines.append(f"  Rodando: {', '.join(running)}")
    if error:
        summary_lines.append(f"  Com erro: {', '.join(error)}")
    if idle:
        summary_lines.append(f"  Ociosos: {', '.join(idle)}")

    # Recent tasks
    tasks_res = (
        supabase.table("runtime_tasks")
        .select("task_type, status, created_at")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    tasks = tasks_res.data or []
    pending = sum(1 for t in tasks if t["status"] == "pending")
    done = sum(1 for t in tasks if t["status"] == "done")
    failed = sum(1 for t in tasks if t["status"] == "failed")

    summary_lines.append(f"\nÚltimas 10 tasks: {done} concluídas, {pending} pendentes, {failed} com falha")

    # LLM cost today
    cost_res = (
        supabase.table("llm_cost_log")
        .select("cost_usd")
        .gte("created_at", _today_start())
        .execute()
    )
    total_cost = sum(float(r["cost_usd"]) for r in (cost_res.data or []))
    summary_lines.append(f"\nCusto de API hoje: USD {total_cost:.4f}")

    message = "\n".join(summary_lines)
    return {"message": message, "agents": agents, "recent_tasks": tasks}


def _today_start() -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
