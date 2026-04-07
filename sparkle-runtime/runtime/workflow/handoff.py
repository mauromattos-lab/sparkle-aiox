"""
Hierarchical 3-Level Handoff System — B2-05

Three handoff levels:
  1. Local  — within the same workflow/task pipeline. Direct call, data passes
              through workflow context. Example: brain_ingest -> extract_insights.
  2. Layer  — cross-workflow/domain. Creates a new runtime_task with proper
              context transfer. Example: content workflow needs brain query.
  3. Global — escalation to orchestrator (Orion). Includes fallback: if target
              unavailable, queues for later. Example: dev -> architect decision.

All handoffs are logged in handoff_log for full observability.

Usage:
    from runtime.workflow.handoff import local_handoff, layer_handoff, global_handoff

    # Local: next step in same pipeline
    result = await local_handoff(current_task, "extract_insights", {"chunks": [...]})

    # Layer: cross-domain request
    result = await layer_handoff("content_gen", "brain", "brain_query", {"query": "..."})

    # Global: escalation
    result = await global_handoff("dev", "architecture decision needed", {...}, priority="high")
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_payload(payload: dict, max_len: int = 200) -> str:
    """Create a short summary of a payload for the log."""
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
        return text[:max_len]
    except Exception:
        return str(payload)[:max_len]


# ── Handoff Log ──────────────────────────────────────────────────────

async def _log_handoff(
    source_agent: str,
    target_agent: str,
    level: str,
    intent: str | None = None,
    status: str = "pending",
    payload_summary: str | None = None,
    task_id: str | None = None,
    parent_task_id: str | None = None,
    error: str | None = None,
) -> str | None:
    """Insert a row in handoff_log. Returns the log entry id."""
    try:
        row = {
            "source_agent": source_agent,
            "target_agent": target_agent,
            "handoff_level": level,
            "intent": intent,
            "status": status,
            "payload_summary": payload_summary,
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "error": error,
        }
        if status in ("completed", "failed"):
            row["completed_at"] = _now()

        result = await asyncio.to_thread(
            lambda: supabase.table("handoff_log").insert(row).execute()
        )
        entry_id = result.data[0]["id"] if result.data else None
        logger.info(
            "[handoff] logged: %s -> %s (level=%s, status=%s, id=%s)",
            source_agent, target_agent, level, status, entry_id,
        )
        return entry_id
    except Exception as exc:
        logger.error("[handoff] failed to log handoff: %s", exc)
        return None


async def _update_handoff_log(handoff_id: str, data: dict) -> None:
    """Update an existing handoff_log entry."""
    try:
        data["completed_at"] = _now() if data.get("status") in ("completed", "failed", "escalated") else None
        await asyncio.to_thread(
            lambda: supabase.table("handoff_log").update(data).eq("id", handoff_id).execute()
        )
    except Exception as exc:
        logger.error("[handoff] failed to update log %s: %s", handoff_id, exc)


# ── Level 1: Local Handoff ───────────────────────────────────────────

async def local_handoff(
    current_task: dict,
    next_handler: str,
    context: dict,
) -> dict:
    """
    Within-workflow handoff. Calls the next handler directly in the same
    execution context. Data passes through without creating a new task row.

    Args:
        current_task: The currently executing task dict.
        next_handler: Task type string for the next handler (e.g. "extract_insights").
        context: Data to pass to the next handler (merged into a synthetic task).

    Returns:
        Result dict from the next handler.
    """
    from runtime.tasks.registry import get_handler

    source_agent = current_task.get("agent_id", "system")
    parent_task_id = str(current_task.get("id", ""))

    handler = get_handler(next_handler)
    if not handler:
        error_msg = f"No handler registered for '{next_handler}'"
        await _log_handoff(
            source_agent=source_agent,
            target_agent=next_handler,
            level="local",
            intent=f"local_handoff -> {next_handler}",
            status="failed",
            error=error_msg,
            parent_task_id=parent_task_id,
        )
        return {"error": error_msg, "handoff_level": "local", "status": "failed"}

    # Build a synthetic task for the next handler
    synthetic_task = {
        **current_task,
        "task_type": next_handler,
        "payload": {
            **(current_task.get("payload") or {}),
            **context,
            "parent_task_id": parent_task_id,
            "parent_task_type": current_task.get("task_type", ""),
            "handoff_level": "local",
        },
    }

    handoff_id = await _log_handoff(
        source_agent=source_agent,
        target_agent=next_handler,
        level="local",
        intent=f"local_handoff -> {next_handler}",
        status="accepted",
        payload_summary=_summarize_payload(context),
        parent_task_id=parent_task_id,
    )

    try:
        result = await handler(synthetic_task)
        if handoff_id:
            await _update_handoff_log(handoff_id, {"status": "completed"})
        return {
            **(result if isinstance(result, dict) else {"result": result}),
            "handoff_level": "local",
            "handoff_status": "completed",
        }
    except Exception as exc:
        logger.error("[handoff] local handoff to '%s' failed: %s", next_handler, exc)
        if handoff_id:
            await _update_handoff_log(handoff_id, {"status": "failed", "error": str(exc)})
        return {
            "error": str(exc),
            "handoff_level": "local",
            "handoff_status": "failed",
        }


# ── Level 2: Layer Handoff ───────────────────────────────────────────

async def layer_handoff(
    source_agent: str,
    target_agent: str,
    intent: str,
    payload: dict,
    client_id: str | None = None,
    priority: int = 7,
    parent_task_id: str | None = None,
) -> dict:
    """
    Cross-workflow handoff. Creates a new runtime_task for the target agent
    with proper context transfer.

    Args:
        source_agent: Slug of the requesting agent.
        target_agent: Task type (handler) that should process this.
        intent: What the source agent needs (human-readable).
        payload: Data to pass to the target handler.
        client_id: Optional client context.
        priority: Task priority (1=low, 10=high).
        parent_task_id: ID of the originating task, for traceability.

    Returns:
        Dict with created task_id and handoff log info.
    """
    effective_client_id = client_id or settings.sparkle_internal_client_id

    # Create the cross-domain task
    task_data = {
        "agent_id": source_agent,
        "client_id": effective_client_id,
        "task_type": target_agent,
        "payload": {
            **payload,
            "handoff_source": source_agent,
            "handoff_intent": intent,
            "handoff_level": "layer",
            "parent_task_id": parent_task_id,
        },
        "status": "pending",
        "priority": priority,
    }

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert(task_data).execute()
        )
        task_id = result.data[0]["id"] if result.data else None
    except Exception as exc:
        logger.error("[handoff] layer handoff failed to create task: %s", exc)
        await _log_handoff(
            source_agent=source_agent,
            target_agent=target_agent,
            level="layer",
            intent=intent,
            status="failed",
            payload_summary=_summarize_payload(payload),
            error=str(exc),
            parent_task_id=parent_task_id,
        )
        return {
            "error": str(exc),
            "handoff_level": "layer",
            "handoff_status": "failed",
        }

    handoff_id = await _log_handoff(
        source_agent=source_agent,
        target_agent=target_agent,
        level="layer",
        intent=intent,
        status="pending",
        payload_summary=_summarize_payload(payload),
        task_id=task_id,
        parent_task_id=parent_task_id,
    )

    logger.info(
        "[handoff] layer: %s -> %s (intent=%s, task=%s)",
        source_agent, target_agent, intent, task_id,
    )

    return {
        "task_id": task_id,
        "handoff_id": handoff_id,
        "handoff_level": "layer",
        "handoff_status": "pending",
        "intent": intent,
    }


# ── Level 3: Global Handoff (Escalation) ─────────────────────────────

PRIORITY_MAP = {"low": 3, "normal": 5, "high": 8, "critical": 10}


async def global_handoff(
    source_agent: str,
    issue: str,
    context: dict,
    priority: str = "normal",
    parent_task_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    """
    Escalation to the orchestrator (Orion/system). When an agent cannot
    resolve something, it escalates up.

    Fallback logic: if the escalation target is not available (no handler
    registered), the handoff is queued with status='escalated' for later
    processing.

    Args:
        source_agent: Who is escalating.
        issue: Description of the issue / what's needed.
        context: Full context dict for the orchestrator.
        priority: "low", "normal", "high", "critical".
        parent_task_id: Originating task.
        client_id: Optional client scope.

    Returns:
        Dict with escalation info.
    """
    effective_client_id = client_id or settings.sparkle_internal_client_id
    numeric_priority = PRIORITY_MAP.get(priority, 5)

    # Try to resolve the best target via agent routing
    target_info = await resolve_handoff_target(intent=issue, source_agent=source_agent)
    target_agent = target_info.get("agent_id", "orion") if target_info else "orion"
    target_task_type = target_info.get("task_type", "conclave") if target_info else "conclave"

    # Create escalation task
    task_data = {
        "agent_id": target_agent,
        "client_id": effective_client_id,
        "task_type": target_task_type,
        "payload": {
            **context,
            "escalation_source": source_agent,
            "escalation_issue": issue,
            "escalation_priority": priority,
            "handoff_level": "global",
            "parent_task_id": parent_task_id,
        },
        "status": "pending",
        "priority": numeric_priority,
    }

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert(task_data).execute()
        )
        task_id = result.data[0]["id"] if result.data else None
        status = "pending"
    except Exception as exc:
        logger.error("[handoff] global escalation failed to create task: %s", exc)
        task_id = None
        status = "escalated"  # queued for later — fallback

    handoff_id = await _log_handoff(
        source_agent=source_agent,
        target_agent=target_agent,
        level="global",
        intent=issue,
        status=status,
        payload_summary=_summarize_payload(context),
        task_id=task_id,
        parent_task_id=parent_task_id,
        error="escalation queued — task creation failed" if status == "escalated" else None,
    )

    logger.info(
        "[handoff] global: %s -> %s (issue=%s, priority=%s, task=%s, status=%s)",
        source_agent, target_agent, issue, priority, task_id, status,
    )

    return {
        "task_id": task_id,
        "handoff_id": handoff_id,
        "target_agent": target_agent,
        "handoff_level": "global",
        "handoff_status": status,
        "issue": issue,
        "priority": priority,
    }


# ── Target Resolution ─────────────────────────────────────────────────

async def resolve_handoff_target(
    intent: str,
    source_agent: str,
) -> Optional[dict[str, Any]]:
    """
    Use agent routing to find the best target for a handoff.

    Tries the routing table first. If no match, falls back to
    well-known mappings for common intents.

    Returns:
        {"agent_id": "...", "task_type": "...", "slug": "..."} or None.
    """
    # Try the DB-based agent routing first
    try:
        from runtime.agents.routing import resolve_agent
        agent = await resolve_agent(intent=intent)
        if agent:
            # Map agent to a reasonable task type
            slug = agent.get("slug", "")
            task_type = _agent_slug_to_task_type(slug)
            return {
                "agent_id": slug or agent.get("agent_id", "system"),
                "task_type": task_type,
                "slug": slug,
                "display_name": agent.get("display_name", ""),
            }
    except Exception as exc:
        logger.warning("[handoff] agent routing lookup failed: %s", exc)

    # Fallback: well-known intent -> agent mappings
    FALLBACK_MAP = {
        "architecture": {"agent_id": "architect", "task_type": "conclave", "slug": "architect"},
        "deploy": {"agent_id": "devops", "task_type": "activate_agent", "slug": "devops"},
        "quality": {"agent_id": "qa", "task_type": "conclave", "slug": "qa"},
        "brain_query": {"agent_id": "system", "task_type": "brain_query", "slug": "system"},
        "brain_ingest": {"agent_id": "system", "task_type": "brain_ingest", "slug": "system"},
        "content": {"agent_id": "system", "task_type": "generate_content", "slug": "system"},
    }

    # Check if any fallback key is a substring of the intent
    intent_lower = intent.lower()
    for key, mapping in FALLBACK_MAP.items():
        if key in intent_lower:
            logger.info("[handoff] resolved via fallback: intent='%s' -> %s", intent, mapping)
            return mapping

    # No match — caller should default to orion/conclave
    return None


def _agent_slug_to_task_type(slug: str) -> str:
    """Map an agent slug to the most appropriate default task type."""
    SLUG_MAP = {
        "friday": "chat",
        "orion": "conclave",
        "architect": "conclave",
        "dev": "activate_agent",
        "qa": "conclave",
        "analyst": "conclave",
        "pm": "conclave",
        "po": "conclave",
        "sm": "conclave",
        "devops": "activate_agent",
    }
    return SLUG_MAP.get(slug, "conclave")


# ── Process Handoff from Task Result ──────────────────────────────────

async def process_handoff_directive(
    directive: dict,
    source_task: dict,
) -> dict:
    """
    Process a handoff directive returned by a task handler.

    Expected directive format:
        {
            "target": "brain_query",       # target handler/agent
            "intent": "need brain context", # what's needed
            "level": "layer",              # local | layer | global
            "payload": {...},              # optional extra data
            "priority": "normal",          # optional for global
        }

    This is called from the worker when a handler returns {"handoff": {...}}.

    Returns:
        Result dict from the appropriate handoff function.
    """
    level = directive.get("level", "layer")
    target = directive.get("target", "")
    intent = directive.get("intent", f"handoff to {target}")
    payload = directive.get("payload", {})
    priority = directive.get("priority", "normal")

    source_agent = source_task.get("agent_id", "system")
    parent_task_id = str(source_task.get("id", ""))
    client_id = source_task.get("client_id")

    if level == "local":
        return await local_handoff(
            current_task=source_task,
            next_handler=target,
            context=payload,
        )
    elif level == "global":
        return await global_handoff(
            source_agent=source_agent,
            issue=intent,
            context=payload,
            priority=priority,
            parent_task_id=parent_task_id,
            client_id=client_id,
        )
    else:
        # Default to layer
        return await layer_handoff(
            source_agent=source_agent,
            target_agent=target,
            intent=intent,
            payload=payload,
            client_id=client_id,
            priority=PRIORITY_MAP.get(priority, 7) if isinstance(priority, str) else priority,
            parent_task_id=parent_task_id,
        )
