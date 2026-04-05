"""
Task worker — ARQ-based async worker + in-process polling fallback.

Two modes:
1. ARQ worker (production): run `arq runtime.tasks.worker.WorkerSettings`
2. In-process polling (development / when Redis isn't available):
   the /tasks/poll endpoint processes one pending task synchronously.

Both update runtime_tasks status in Supabase.

S9: Brain Gate — todo task cognitivo busca contexto no Brain antes de executar.
Task types em BRAIN_EXEMPT ficam fora do gate (operacionais, não cognitivos).
Se Brain retornar erro: task vai para retry — nunca executa sem contexto.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter
from arq import cron
from arq.connections import RedisSettings

from runtime.brain.embedding import get_embedding
from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.registry import get_handler

router = APIRouter()

# Task types que NÃO precisam de contexto Brain para executar
# (operacionais, não cognitivos)
BRAIN_EXEMPT_TASK_TYPES = frozenset({
    "echo",
    "health_alert",
    "conversation_summary",
    "loja_integrada_query",
    "send_character_message",
    "workflow_step",
    "brain_ingest_pipeline",  # SYS-1.3: pipeline faz suas proprias operacoes Brain
    "extract_dna",            # SYS-1.3: sub-task da pipeline, nao precisa de gate
    "narrative_synthesis",    # SYS-1.3: sub-task da pipeline, nao precisa de gate
    "extract_client_dna",     # SYS-4: extracao de DNA do cliente
    "observer_gap_analysis",  # SYS-5: analise de gaps do sistema
    "auto_implement_gap",     # SYS-5: implementacao automatica de gaps
    "extract_insights",       # Brain Fase 5: extrai insights de chunks
    "cross_source_synthesis", # Brain Fase 6: sintese cruzada por dominio
    "pipeline_gate",              # C2-B2: pipeline enforcement gate step
    "pipeline_violation_alert",   # C2-B2: pipeline violation notification
})


# ── Brain Gate ──────────────────────────────────────────────

async def _fetch_brain_context(namespace: str, query: str) -> dict:
    """
    Busca contexto relevante no Brain para este task.
    Lança exceção se Brain inacessível — worker coloca task em retry.
    Retorna dict com chunks e context_id do chunk mais relevante.
    """
    try:
        embedding = await get_embedding(query)

        if embedding:
            result = await asyncio.to_thread(
                lambda: supabase.rpc(
                    "match_brain_chunks",
                    {"query_embedding": embedding, "pipeline_type_in": "mauro", "client_id_in": None, "match_count": 5},
                ).execute()
            )
            chunks = result.data or []
        else:
            # Fallback: text search se embedding não disponível
            words = [w for w in query.split() if len(w) > 3][:3] or query.split()[:2]
            first_word = words[0] if words else query[:20]
            result = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id,raw_content,source_type,source_title")
                .ilike("raw_content", f"%{first_word}%")
                .limit(5)
                .execute()
            )
            chunks = result.data or []

        context_id = chunks[0]["id"] if chunks else None
        score = chunks[0].get("similarity") if chunks else None
        return {"chunks": chunks, "context_id": context_id, "score": score}

    except Exception as e:
        print(f"[worker] Brain Gate: falha ao buscar contexto — {e}")
        raise


# ── Core executor ──────────────────────────────────────────

async def execute_task(task: dict) -> None:
    """
    Execute a single task asynchronously.
    S9: injeta contexto Brain antes de executar (exceto tasks em BRAIN_EXEMPT).
    Updates Supabase status: running → done | failed.
    """
    task_id = task["id"]
    task_type = task.get("task_type", "")

    # ── S9 Brain Gate ──
    if task_type not in BRAIN_EXEMPT_TASK_TYPES:
        namespace = task.get("client_id") or settings.sparkle_internal_client_id or "sparkle-internal"
        query = (
            task.get("payload", {}).get("summary")
            or task.get("payload", {}).get("original_text", "")[:200]
            or task_type
        )
        try:
            brain_ctx = await _fetch_brain_context(namespace=namespace, query=query)
            task["brain_context"] = brain_ctx.get("chunks", [])
            # Persiste brain_context_id antes de executar
            await _update_task(task_id, {
                "brain_context_id": brain_ctx.get("context_id"),
                "brain_context_score": brain_ctx.get("score"),
            })
        except Exception:
            # Brain inacessível: task vai para retry — nunca executa sem contexto
            retry_count = task.get("retry_count", 0)
            max_retries = task.get("max_retries", 3)
            if retry_count < max_retries:
                await _update_task(task_id, {
                    "status": "pending",
                    "retry_count": retry_count + 1,
                    "error": "brain_unavailable — retrying",
                })
            else:
                await _update_task(task_id, {
                    "status": "failed",
                    "error": "brain_unavailable after max retries",
                    "completed_at": _now(),
                })
            return
    # ── fim Brain Gate ──

    # ── C2-B2 Pipeline Enforcement ──────────────────────────────
    # If this task has a workflow_run_id linked to an aios_pipeline,
    # verify the pipeline allows execution at the current step.
    workflow_run_id = task.get("workflow_run_id")
    if workflow_run_id and task_type not in BRAIN_EXEMPT_TASK_TYPES:
        try:
            from runtime.workflows.pipeline_enforcement import check_gates, notify_violation, get_step_name
            wr_result = await asyncio.to_thread(
                lambda: supabase.table("workflow_runs")
                .select("workflow_type,current_step")
                .eq("id", workflow_run_id)
                .single()
                .execute()
            )
            wr = wr_result.data if wr_result.data else None
            if wr and wr.get("workflow_type") == "aios_pipeline":
                target_step = task.get("payload", {}).get("pipeline_target_step")
                if target_step is None:
                    # Tasks linked to aios_pipeline MUST declare their target step
                    await _update_task(task_id, {
                        "status": "failed",
                        "error": "Pipeline violation: task linked to aios_pipeline but missing pipeline_target_step in payload",
                        "completed_at": _now(),
                    })
                    print(f"[worker] Task {task_id} blocked: missing pipeline_target_step for aios_pipeline")
                    return
                gate_check = await check_gates(workflow_run_id, target_step)
                if not gate_check["allowed"]:
                    item_id = task.get("payload", {}).get("item_id", str(task_id))
                    agent = task.get("agent_id", "unknown")
                    await notify_violation(
                        item_id=item_id,
                        current_step=wr.get("current_step", 0),
                        attempted_step=target_step,
                        agent=agent,
                    )
                    await _update_task(task_id, {
                        "status": "failed",
                        "error": f"Pipeline violation: {gate_check['reason']}",
                        "completed_at": _now(),
                    })
                    print(f"[worker] Task {task_id} blocked by pipeline enforcement: {gate_check['reason']}")
                    return
        except Exception as e:
            print(f"[worker] Pipeline check error (non-blocking): {e}")
    # ── fim Pipeline Enforcement ──

    # ── Gate Enforcement ──────────────────────────────────────
    required_gates: list = task.get("required_gates") or []
    gates_cleared: list = task.get("gates_cleared") or []
    if required_gates:
        pending_gates = [g for g in required_gates if g not in gates_cleared]
        if pending_gates:
            await _update_task(task_id, {
                "status": "awaiting_gate",
                "error": f"Aguardando aprovação de: {', '.join(pending_gates)}",
            })
            print(f"[worker] Task {task_id} bloqueada em gate(s): {pending_gates}")
            return
    # ── fim Gate Enforcement ──

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
        update_data: dict = {
            "status": "done",
            "result": result,
            "error": None,
            "completed_at": _now(),
        }
        # handoff_acknowledged: marca quando a task gerou handoff esperando próximo agente
        if isinstance(result, dict) and result.get("handoff_to"):
            update_data["handoff_acknowledged"] = None  # NULL = aguardando ack do próximo
        await _update_task(task_id, update_data)

        # ── B2-05 Hierarchical Handoff Engine ─────────────────────────────────
        # Supports two patterns:
        #   1. Legacy flat: result has "handoff_to" -> creates next task (backwards compatible)
        #   2. New 3-level: result has "handoff" dict with target/intent/level
        if isinstance(result, dict) and result.get("handoff"):
            # New 3-level handoff system
            from runtime.workflow.handoff import process_handoff_directive
            handoff_directive = result["handoff"]
            handoff_result = await process_handoff_directive(
                directive=handoff_directive,
                source_task=task,
            )
            print(f"[worker] B2-05 handoff processed: level={handoff_directive.get('level')} "
                  f"target={handoff_directive.get('target')} "
                  f"status={handoff_result.get('handoff_status')}")
        elif isinstance(result, dict) and result.get("handoff_to"):
            # Legacy flat handoff — backwards compatible
            effective_client_id = task.get("client_id") or settings.sparkle_internal_client_id
            await _create_handoff_task(
                task_type=result["handoff_to"],
                payload={
                    **(result.get("handoff_payload") or {}),
                    "parent_task_id": str(task_id),
                    "parent_task_type": task_type,
                },
                client_id=effective_client_id,
                priority=task.get("priority", 7),
            )

        # ── Auto-Brain-Ingest ──────────────────────────────────────────────────
        # Se o result for brain_worthy, ingere o conteúdo no Brain automaticamente
        # com baixa prioridade — sem bloquear o fluxo principal.
        if isinstance(result, dict) and result.get("brain_worthy"):
            content = result.get("brain_content") or result.get("message", "")
            if content and len(content) > 50:
                effective_client_id = task.get("client_id") or settings.sparkle_internal_client_id
                await _create_handoff_task(
                    task_type="brain_ingest",
                    payload={
                        "content": content[:4000],
                        "source_agent": task.get("agent_id", "system"),
                        "ingest_type": "agent_output",
                        "source_title": f"auto:{task_type}",
                        "parent_task_id": str(task_id),
                    },
                    client_id=effective_client_id,
                    priority=3,  # baixa prioridade — não urgente
                )
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


async def _create_handoff_task(task_type: str, payload: dict, client_id: str, priority: int = 7) -> str | None:
    """Cria task de handoff automaticamente ao completar task pai."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "system",
                "client_id": client_id,
                "task_type": task_type,
                "payload": payload,
                "status": "pending",
                "priority": priority,
            }).execute()
        )
        handoff_id = result.data[0]["id"] if result.data else None
        print(f"[worker] handoff criado: {task_type} → task_id={handoff_id}")
        return handoff_id
    except Exception as e:
        print(f"[worker] falha ao criar handoff task {task_type}: {e}")
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Gate Approval endpoint ─────────────────────────────────

@router.post("/{task_id}/gate/clear")
async def clear_gate(task_id: str, gate: str, approved_by: str = "system"):
    """
    Aprova um gate específico em uma task awaiting_gate.
    Quando todos os gates estiverem cleared, task volta para pending.

    Exemplo: POST /tasks/{id}/gate/clear?gate=qa&approved_by=@qa
    """
    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("required_gates,gates_cleared,status")
        .eq("id", task_id)
        .single()
        .execute()
    )
    task = result.data
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task não encontrada")

    required: list = task.get("required_gates") or []
    cleared: list = task.get("gates_cleared") or []

    if gate not in required:
        return {"status": "ignored", "reason": f"gate '{gate}' não está em required_gates"}

    if gate not in cleared:
        cleared = cleared + [gate]

    pending = [g for g in required if g not in cleared]
    new_status = "pending" if not pending else "awaiting_gate"

    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").update({
            "gates_cleared": cleared,
            "status": new_status,
            "error": None if new_status == "pending" else f"Aguardando: {', '.join(pending)}",
            "updated_at": _now(),
        }).eq("id", task_id).execute()
    )

    print(f"[gate] Task {task_id}: gate '{gate}' cleared by {approved_by}. Pending: {pending}")
    return {
        "task_id": task_id,
        "gate_cleared": gate,
        "approved_by": approved_by,
        "gates_pending": pending,
        "task_status": new_status,
    }


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


async def trigger_weekly_briefing(ctx: dict) -> None:
    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "weekly_briefing",
            "payload": {"source": "cron_sunday_8h_brasilia"},
            "status": "pending",
            "priority": 8,
        }).execute()
    )
    task_id = task.data[0]["id"] if task.data else None
    print(f"[worker] weekly_briefing triggered — task_id={task_id}")


async def trigger_gap_report(ctx: dict) -> None:
    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "gap_report",
            "payload": {"source": "cron_monday_8h_brasilia"},
            "status": "pending",
            "priority": 7,
        }).execute()
    )
    task_id = task.data[0]["id"] if task.data else None
    print(f"[worker] gap_report triggered — task_id={task_id}")


async def trigger_health_check(ctx: dict) -> None:
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


async def trigger_weekly_content(ctx: dict) -> None:
    """
    Gera 3 conteúdos semanais automaticamente (sexta 9h Brasília = 12h UTC):
    - post sobre atendimento automático (persona zenya)
    - carrossel sobre crescimento digital (persona zenya)
    - thread sobre IA para negócios (persona mauro)
    """
    topics = [
        {"topic": "atendimento automático transforma o relacionamento com clientes", "format": "instagram_post", "persona": "zenya"},
        {"topic": "como crescer com presença digital inteligente", "format": "carousel", "persona": "zenya"},
        {"topic": "o papel da IA no crescimento de negócios em 2025", "format": "thread", "persona": "mauro"},
    ]
    task_ids = []
    for t in topics:
        result = await asyncio.to_thread(
            lambda tt=t: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "generate_content",
                "payload": {**tt, "source_type": "cron", "source_ref": "cron_friday_9h"},
                "status": "pending",
                "priority": 5,
            }).execute()
        )
        tid = result.data[0]["id"] if result.data else None
        task_ids.append(tid)
    print(f"[worker] weekly_content triggered — {len(task_ids)} tasks: {task_ids}")


class WorkerSettings:
    # Only process_pending_tasks runs via ARQ cron.
    # All other scheduled jobs (daily_briefing, weekly_briefing, gap_report,
    # health_check, weekly_content) are handled by APScheduler in scheduler.py.
    # Keeping them here would cause duplicate execution. (P1-6 fix)
    functions = [process_pending_tasks]
    cron_jobs = [
        cron(process_pending_tasks, second={0, 15, 30, 45}),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 600  # 10 min — extract_dna/narrative_synthesis fazem chamadas Haiku por chunk
