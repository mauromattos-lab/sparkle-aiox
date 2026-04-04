"""
Unit tests for B2-05 Hierarchical 3-Level Handoff System.
Tests local_handoff, layer_handoff, global_handoff, resolve_handoff_target,
and process_handoff_directive.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────

def _mock_supabase_insert(return_id="fake-handoff-id-001"):
    """Create a mock that simulates supabase.table(...).insert(...).execute()."""
    mock_response = MagicMock()
    mock_response.data = [{"id": return_id}]

    mock_query = MagicMock()
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value = mock_response

    mock_client = MagicMock()
    mock_client.table.return_value = mock_query
    return mock_client


def _make_task(**overrides):
    base = {
        "id": "task-001",
        "agent_id": "dev",
        "client_id": "sparkle-internal",
        "task_type": "echo",
        "payload": {"content": "test"},
    }
    base.update(overrides)
    return base


# ── local_handoff ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_handoff_calls_handler_directly():
    """Local handoff should call the target handler without creating a DB task."""
    mock_handler = AsyncMock(return_value={"message": "extracted insights"})

    with patch("runtime.tasks.registry.get_handler", return_value=mock_handler), \
         patch("runtime.workflow.handoff.supabase", _mock_supabase_insert()):
        from runtime.workflow.handoff import local_handoff

        task = _make_task()
        result = await local_handoff(task, "extract_insights", {"chunks": [1, 2, 3]})

    assert result["handoff_level"] == "local"
    assert result["handoff_status"] == "completed"
    assert result["message"] == "extracted insights"
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_local_handoff_missing_handler():
    """Local handoff to a non-existent handler should return error."""
    with patch("runtime.tasks.registry.get_handler", return_value=None), \
         patch("runtime.workflow.handoff.supabase", _mock_supabase_insert()):
        from runtime.workflow.handoff import local_handoff

        task = _make_task()
        result = await local_handoff(task, "nonexistent_handler", {})

    assert result["handoff_level"] == "local"
    assert result["status"] == "failed"
    assert "No handler" in result["error"]


@pytest.mark.asyncio
async def test_local_handoff_handler_exception():
    """Local handoff should catch handler exceptions and return failed."""
    mock_handler = AsyncMock(side_effect=ValueError("boom"))

    with patch("runtime.tasks.registry.get_handler", return_value=mock_handler), \
         patch("runtime.workflow.handoff.supabase", _mock_supabase_insert()):
        from runtime.workflow.handoff import local_handoff

        task = _make_task()
        result = await local_handoff(task, "extract_insights", {})

    assert result["handoff_status"] == "failed"
    assert "boom" in result["error"]


# ── layer_handoff ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_layer_handoff_creates_task():
    """Layer handoff should create a new runtime_task in Supabase."""
    mock_sb = _mock_supabase_insert("layer-task-001")

    with patch("runtime.workflow.handoff.supabase", mock_sb):
        from runtime.workflow.handoff import layer_handoff

        result = await layer_handoff(
            source_agent="content_gen",
            target_agent="brain_query",
            intent="need brain context for content",
            payload={"query": "sparkle brand voice"},
        )

    assert result["handoff_level"] == "layer"
    assert result["handoff_status"] == "pending"
    assert result["task_id"] == "layer-task-001"
    assert result["intent"] == "need brain context for content"


@pytest.mark.asyncio
async def test_layer_handoff_db_failure():
    """Layer handoff should handle DB insert failure gracefully."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_table
    mock_table.execute.side_effect = Exception("DB connection lost")
    mock_sb.table.return_value = mock_table

    with patch("runtime.workflow.handoff.supabase", mock_sb):
        from runtime.workflow.handoff import layer_handoff

        result = await layer_handoff(
            source_agent="dev",
            target_agent="brain_query",
            intent="test",
            payload={},
        )

    assert result["handoff_status"] == "failed"
    assert "DB connection lost" in result["error"]


# ── global_handoff ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_global_handoff_escalates_to_orion():
    """Global handoff should create an escalation task targeting orion."""
    mock_sb = _mock_supabase_insert("escalation-task-001")

    with patch("runtime.workflow.handoff.supabase", mock_sb), \
         patch("runtime.workflow.handoff.resolve_handoff_target", new_callable=AsyncMock, return_value=None):
        from runtime.workflow.handoff import global_handoff

        result = await global_handoff(
            source_agent="dev",
            issue="architecture decision needed for brain schema",
            context={"decision": "which embedding provider"},
            priority="high",
        )

    assert result["handoff_level"] == "global"
    assert result["target_agent"] == "orion"
    assert result["handoff_status"] == "pending"
    assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_global_handoff_with_resolved_target():
    """Global handoff should use routing to find specialist if available."""
    mock_sb = _mock_supabase_insert("architect-task-001")
    resolved = {"agent_id": "architect", "task_type": "conclave", "slug": "architect"}

    with patch("runtime.workflow.handoff.supabase", mock_sb), \
         patch("runtime.workflow.handoff.resolve_handoff_target", new_callable=AsyncMock, return_value=resolved):
        from runtime.workflow.handoff import global_handoff

        result = await global_handoff(
            source_agent="dev",
            issue="architecture decision needed",
            context={},
        )

    assert result["target_agent"] == "architect"


@pytest.mark.asyncio
async def test_global_handoff_queues_on_failure():
    """If task creation fails, global handoff should queue with 'escalated' status."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_table

    call_count = [0]
    def side_effect():
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: runtime_tasks insert fails
            raise Exception("DB down")
        # Second call: handoff_log insert succeeds
        return MagicMock(data=[{"id": "log-001"}])

    mock_table.execute.side_effect = side_effect
    mock_sb.table.return_value = mock_table

    with patch("runtime.workflow.handoff.supabase", mock_sb), \
         patch("runtime.workflow.handoff.resolve_handoff_target", new_callable=AsyncMock, return_value=None):
        from runtime.workflow.handoff import global_handoff

        result = await global_handoff(
            source_agent="dev",
            issue="critical failure",
            context={},
            priority="critical",
        )

    assert result["handoff_status"] == "escalated"
    assert result["task_id"] is None


# ── resolve_handoff_target ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_handoff_target_fallback():
    """Should use fallback map when DB routing fails."""
    with patch("runtime.agents.routing.resolve_agent", new_callable=AsyncMock, side_effect=Exception("no DB")):
        from runtime.workflow.handoff import resolve_handoff_target

        result = await resolve_handoff_target(intent="architecture review", source_agent="dev")

    assert result is not None
    assert result["agent_id"] == "architect"


@pytest.mark.asyncio
async def test_resolve_handoff_target_no_match():
    """Should return None if no match in routing or fallback."""
    with patch("runtime.agents.routing.resolve_agent", new_callable=AsyncMock, return_value=None):
        from runtime.workflow.handoff import resolve_handoff_target

        result = await resolve_handoff_target(intent="something_completely_unknown", source_agent="dev")

    assert result is None


# ── process_handoff_directive ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_directive_local():
    """Process a local handoff directive from a task result."""
    mock_handler = AsyncMock(return_value={"message": "done"})

    with patch("runtime.tasks.registry.get_handler", return_value=mock_handler), \
         patch("runtime.workflow.handoff.supabase", _mock_supabase_insert()):
        from runtime.workflow.handoff import process_handoff_directive

        result = await process_handoff_directive(
            directive={"target": "extract_insights", "intent": "extract", "level": "local", "payload": {}},
            source_task=_make_task(),
        )

    assert result["handoff_level"] == "local"
    assert result["handoff_status"] == "completed"


@pytest.mark.asyncio
async def test_process_directive_layer():
    """Process a layer handoff directive from a task result."""
    mock_sb = _mock_supabase_insert("directive-task-001")

    with patch("runtime.workflow.handoff.supabase", mock_sb):
        from runtime.workflow.handoff import process_handoff_directive

        result = await process_handoff_directive(
            directive={"target": "brain_query", "intent": "need data", "level": "layer"},
            source_task=_make_task(),
        )

    assert result["handoff_level"] == "layer"
    assert result["task_id"] == "directive-task-001"


@pytest.mark.asyncio
async def test_process_directive_global():
    """Process a global handoff directive from a task result."""
    mock_sb = _mock_supabase_insert("global-task-001")

    with patch("runtime.workflow.handoff.supabase", mock_sb), \
         patch("runtime.workflow.handoff.resolve_handoff_target", new_callable=AsyncMock, return_value=None):
        from runtime.workflow.handoff import process_handoff_directive

        result = await process_handoff_directive(
            directive={
                "target": "orion",
                "intent": "need strategic decision",
                "level": "global",
                "priority": "high",
            },
            source_task=_make_task(),
        )

    assert result["handoff_level"] == "global"


@pytest.mark.asyncio
async def test_process_directive_defaults_to_layer():
    """If level is not specified, should default to layer."""
    mock_sb = _mock_supabase_insert("default-task-001")

    with patch("runtime.workflow.handoff.supabase", mock_sb):
        from runtime.workflow.handoff import process_handoff_directive

        result = await process_handoff_directive(
            directive={"target": "brain_query", "intent": "need data"},
            source_task=_make_task(),
        )

    assert result["handoff_level"] == "layer"
