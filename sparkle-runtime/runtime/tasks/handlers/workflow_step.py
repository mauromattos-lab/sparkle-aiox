"""
workflow_step handler — executa um step de workflow declarativo.

Gerencia a execucao de workflows baseados em templates armazenados no Supabase:
1. Carrega instancia e template
2. Resolve {{variable}} no payload_template usando context da instancia
3. Cria task real do step e aguarda resultado via handoff engine
4. Atualiza context da instancia com resultado
5. Retorna handoff_to workflow_step com proximo step_index

Nao substitui a logica existente de handoff no worker.py — adiciona uma camada
declarativa acima para orquestrar workflows completos com templates.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from runtime.db import supabase
from runtime.config import settings


# ── Template resolution ─────────────────────────────────────────────

_VARIABLE_PATTERN = re.compile(r"\{\{(\w[\w.]*)\}\}")


def _resolve_value(path: str, context: dict) -> Any:
    """
    Resolve a dotted path like 'business_name' or 'step_0_result.topics'
    against the context dict. Returns the original {{path}} string if not found.
    """
    parts = path.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            # Path not found — return placeholder as-is for debugging
            return f"{{{{{path}}}}}"
    return current


def _resolve_template(template: Any, context: dict) -> Any:
    """
    Recursively resolve {{variable}} placeholders in a payload template.
    Works on dicts, lists, and strings.
    """
    if isinstance(template, str):
        # If the entire string is a single placeholder, return the raw value
        # (preserves non-string types like booleans, numbers, lists)
        match = _VARIABLE_PATTERN.fullmatch(template)
        if match:
            return _resolve_value(match.group(1), context)

        # Otherwise do string interpolation for embedded placeholders
        def _replace(m: re.Match) -> str:
            val = _resolve_value(m.group(1), context)
            return str(val)

        return _VARIABLE_PATTERN.sub(_replace, template)

    if isinstance(template, dict):
        return {k: _resolve_template(v, context) for k, v in template.items()}

    if isinstance(template, list):
        return [_resolve_template(item, context) for item in template]

    # Numbers, booleans, None — pass through
    return template


# ── Supabase helpers ────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_instance(instance_id: str) -> dict:
    """Load workflow instance from Supabase."""
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .select("*")
        .eq("id", instance_id)
        .single()
        .execute()
    )
    if not result.data:
        raise ValueError(f"Workflow instance '{instance_id}' not found")
    return result.data


async def _get_template(template_id: str) -> dict:
    """Load workflow template from Supabase."""
    result = await asyncio.to_thread(
        lambda: supabase.table("workflow_templates")
        .select("*")
        .eq("id", template_id)
        .single()
        .execute()
    )
    if not result.data:
        raise ValueError(f"Workflow template '{template_id}' not found")
    return result.data


async def _update_instance(instance_id: str, data: dict) -> None:
    """Update workflow instance in Supabase."""
    data["updated_at"] = _now()
    await asyncio.to_thread(
        lambda: supabase.table("workflow_instances")
        .update(data)
        .eq("id", instance_id)
        .execute()
    )


async def _complete_instance(instance_id: str) -> None:
    """Mark workflow instance as completed."""
    await _update_instance(instance_id, {
        "status": "completed",
        "completed_at": _now(),
    })


async def _fail_instance(instance_id: str, error: str) -> None:
    """Mark workflow instance as failed."""
    await _update_instance(instance_id, {
        "status": "failed",
        "completed_at": _now(),
    })


# ── Step execution ──────────────────────────────────────────────────

async def _execute_step_task(
    task_type: str,
    payload: dict,
    agent_id: str,
    client_id: str | None,
    required_gates: list[str],
) -> dict:
    """
    Create a runtime_task for this step, execute it via the registered handler,
    and return the result.
    """
    effective_client_id = client_id or settings.sparkle_internal_client_id

    # Build the task payload — include required_gates if any
    task_payload = {**payload}

    # Create the task record in Supabase
    insert_data = {
        "agent_id": agent_id,
        "client_id": effective_client_id,
        "task_type": task_type,
        "payload": task_payload,
        "status": "running",
        "priority": 7,
        "started_at": _now(),
    }
    if required_gates:
        insert_data["required_gates"] = required_gates

    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .insert(insert_data)
        .execute()
    )

    if not result.data:
        return {"status": "failed", "error": "Failed to create step task"}

    step_task = result.data[0]
    step_task_id = step_task["id"]

    # If the step has required gates, don't execute — let gate system handle it
    if required_gates:
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .update({
                "status": "awaiting_gate",
                "error": f"Aguardando aprovacao de: {', '.join(required_gates)}",
                "updated_at": _now(),
            })
            .eq("id", step_task_id)
            .execute()
        )
        return {
            "status": "awaiting_gate",
            "task_id": step_task_id,
            "gates_pending": required_gates,
            "message": f"Step aguardando gates: {', '.join(required_gates)}",
        }

    # Execute via handler
    from runtime.tasks.registry import get_handler  # lazy import to avoid circular
    handler = get_handler(task_type)
    if not handler:
        error_msg = f"No handler registered for task_type '{task_type}'"
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .update({"status": "failed", "error": error_msg, "completed_at": _now(), "updated_at": _now()})
            .eq("id", step_task_id)
            .execute()
        )
        return {"status": "failed", "error": error_msg}

    try:
        step_result = await handler(step_task)

        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .update({
                "status": "done",
                "result": step_result,
                "completed_at": _now(),
                "updated_at": _now(),
            })
            .eq("id", step_task_id)
            .execute()
        )

        if isinstance(step_result, dict):
            step_result["task_id"] = step_task_id
            step_result["status"] = "done"
        return step_result or {"status": "done", "task_id": step_task_id}

    except Exception as e:
        error_msg = str(e)[:500]
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .update({
                "status": "failed",
                "error": error_msg,
                "completed_at": _now(),
                "updated_at": _now(),
            })
            .eq("id", step_task_id)
            .execute()
        )
        return {"status": "failed", "error": error_msg, "task_id": step_task_id}


# ── Main handler ────────────────────────────────────────────────────

async def handle_workflow_step(task: dict) -> dict:
    """
    Executa um step de workflow declarativo.
    Chamado automaticamente pelo handoff engine ou por POST /workflow/start.

    Payload esperado:
        workflow_instance_id: str  — ID da instancia em execucao
        step_index: int            — indice do step a executar
    """
    payload = task.get("payload", {})
    instance_id = payload.get("workflow_instance_id")
    step_index = payload.get("step_index", 0)

    if not instance_id:
        return {"status": "failed", "error": "Missing workflow_instance_id in payload"}

    try:
        # 1. Load instance and template
        instance = await _get_instance(instance_id)

        # Check instance status — don't execute if paused/cancelled/completed
        instance_status = instance.get("status", "running")
        if instance_status in ("paused", "cancelled", "completed"):
            return {
                "status": "skipped",
                "message": f"Workflow instance is '{instance_status}' — skipping step {step_index}",
            }

        template = await _get_template(instance["template_id"])
        steps = template.get("steps", [])

        # 2. Check if workflow is complete
        if step_index >= len(steps):
            await _complete_instance(instance_id)
            return {
                "message": f"Workflow '{instance['name']}' concluido com sucesso!",
                "workflow_completed": True,
                "workflow_instance_id": instance_id,
            }

        step = steps[step_index]
        context = instance.get("context", {}) or {}

        print(f"[workflow_step] instance={instance_id} step={step_index}/{len(steps)} "
              f"name={step.get('name')} task_type={step.get('task_type')}")

        # 3. Resolve payload template with context variables
        payload_template = step.get("payload_template", {})
        resolved_payload = _resolve_template(payload_template, context)

        # 4. Execute the step task
        result = await _execute_step_task(
            task_type=step["task_type"],
            payload=resolved_payload,
            agent_id=step.get("agent_id", "system"),
            client_id=instance.get("client_id"),
            required_gates=step.get("required_gates", []),
        )

        # 5. Update instance context with step result
        context[f"step_{step_index}_result"] = result
        context[f"step_{step_index}_name"] = step.get("name", f"step_{step_index}")
        await _update_instance(instance_id, {
            "current_step": step_index + 1,
            "context": context,
        })

        # 6. If step is awaiting gate, don't chain — gate approval will resume
        if isinstance(result, dict) and result.get("status") == "awaiting_gate":
            return {
                "message": f"Step '{step.get('name')}' aguardando gate approval",
                "workflow_instance_id": instance_id,
                "step_index": step_index,
                "awaiting_gates": result.get("gates_pending", []),
            }

        # 7. Determine next step
        step_failed = isinstance(result, dict) and result.get("status") == "failed"

        if step_failed:
            on_failure = step.get("on_failure", {})
            if not on_failure.get("continue", False):
                # Failure blocks workflow
                await _fail_instance(instance_id, f"Step {step_index} ({step.get('name')}) failed")
                return {
                    "status": "failed",
                    "message": f"Workflow '{instance['name']}' falhou no step '{step.get('name')}'",
                    "workflow_instance_id": instance_id,
                    "step_error": result.get("error", "unknown"),
                }
            next_step = on_failure.get("next_step", step_index + 1)
        else:
            on_success = step.get("on_success", {})
            next_step = on_success.get("next_step", step_index + 1)

        # 8. No next_step defined (final step)
        if next_step is None or (isinstance(next_step, dict) and not next_step):
            await _complete_instance(instance_id)
            return {
                "message": f"Workflow '{instance['name']}' concluido com sucesso!",
                "workflow_completed": True,
                "workflow_instance_id": instance_id,
            }

        # 9. Parallel steps — create handoff for each
        if isinstance(next_step, list):
            # Create handoff tasks for all parallel branches
            # Return the first one as the direct handoff, create the rest manually
            from runtime.tasks.worker import _create_handoff_task

            for ns in next_step[1:]:
                effective_client_id = instance.get("client_id") or settings.sparkle_internal_client_id
                await _create_handoff_task(
                    task_type="workflow_step",
                    payload={
                        "workflow_instance_id": instance_id,
                        "step_index": ns,
                    },
                    client_id=effective_client_id,
                    priority=task.get("priority", 7),
                )

            return {
                "handoff_to": "workflow_step",
                "handoff_payload": {
                    "workflow_instance_id": instance_id,
                    "step_index": next_step[0],
                },
                "message": f"Step '{step.get('name')}' concluido. Disparando {len(next_step)} steps paralelos.",
            }

        # 10. Sequential next step
        return {
            "handoff_to": "workflow_step",
            "handoff_payload": {
                "workflow_instance_id": instance_id,
                "step_index": next_step,
            },
            "message": f"Step '{step.get('name')}' concluido. Proximo: step {next_step}.",
        }

    except Exception as e:
        print(f"[workflow_step] ERROR: {e}")
        # Try to mark instance as failed
        try:
            if instance_id:
                await _fail_instance(instance_id, str(e)[:500])
        except Exception:
            pass
        return {
            "status": "failed",
            "error": str(e)[:500],
            "workflow_instance_id": instance_id,
            "step_index": step_index,
        }
