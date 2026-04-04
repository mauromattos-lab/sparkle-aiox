"""
Unit tests for health_alert handler.
Mocks: Supabase, Z-API.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

import runtime.tasks.handlers.health_alert as health_alert_mod
from runtime.tasks.handlers.health_alert import handle_health_alert


def _reset_health_state():
    """Reset module-level state between tests."""
    health_alert_mod._last_alert_hash = ""
    health_alert_mod._last_alert_time = None
    health_alert_mod._consecutive_failures = 0


def _make_mock_sb(
    stale_agents=None,
    stuck_tasks=None,
    recent_failures=None,
    rpc_raises=False,
):
    """Build a mock supabase that returns controlled data for health checks."""
    mock_sb = MagicMock()

    stale_agents = stale_agents or []
    stuck_tasks = stuck_tasks or []
    recent_failures = recent_failures or []

    def rpc_fn(name, params=None):
        q = MagicMock()
        if rpc_raises:
            q.execute.side_effect = Exception("RPC not found")
        else:
            resp = MagicMock()
            resp.data = stale_agents
            q.execute.return_value = resp
        return q

    mock_sb.rpc = rpc_fn

    call_count = [0]

    def table_fn(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.lt.return_value = q
        q.gte.return_value = q
        q.update.return_value = q

        if name == "runtime_tasks":
            nonlocal call_count
            call_count[0] += 1
            if call_count[0] == 1:
                # stuck tasks query
                resp = MagicMock()
                resp.data = stuck_tasks
                q.execute.return_value = resp
            elif call_count[0] == 2:
                # recent failures query
                resp = MagicMock()
                resp.data = recent_failures
                q.execute.return_value = resp
            else:
                # update calls
                resp = MagicMock()
                resp.data = []
                q.execute.return_value = resp
        elif name == "agents":
            # fallback for stale heartbeat check
            resp = MagicMock()
            resp.data = stale_agents
            q.execute.return_value = resp
        else:
            resp = MagicMock()
            resp.data = []
            q.execute.return_value = resp

        return q

    mock_sb.table = table_fn
    return mock_sb


# ── Tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_alert_all_ok():
    _reset_health_state()
    mock_sb = _make_mock_sb()

    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
        result = await handle_health_alert({})

    assert result["message"] == "ok"
    assert result["alerts"] == []
    assert result["stuck_resolved"] == 0


@pytest.mark.asyncio
async def test_health_alert_stale_agents():
    _reset_health_state()
    stale = [{"agent_id": "zenya-client-1", "last_heartbeat": "2020-01-01T00:00:00Z", "status": "active"}]
    mock_sb = _make_mock_sb(stale_agents=stale)

    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
        with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            result = await handle_health_alert({})

    assert len(result["alerts"]) >= 1
    assert any("heartbeat" in a.lower() for a in result["alerts"])


@pytest.mark.asyncio
async def test_health_alert_stuck_tasks_auto_resolved():
    _reset_health_state()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    stuck = [
        {"id": "task-stuck-1", "task_type": "chat", "agent_id": "friday", "started_at": old_time},
    ]
    mock_sb = _make_mock_sb(stuck_tasks=stuck)

    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
        with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            result = await handle_health_alert({})

    assert result["stuck_resolved"] >= 1
    assert any("auto-resolvida" in a.lower() for a in result["alerts"])


@pytest.mark.asyncio
async def test_health_alert_many_failures():
    _reset_health_state()
    failures = [{"id": f"f-{i}", "task_type": "chat"} for i in range(8)]
    mock_sb = _make_mock_sb(recent_failures=failures)

    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
        with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            result = await handle_health_alert({})

    assert any("falhas na última hora" in a for a in result["alerts"])


@pytest.mark.asyncio
async def test_health_alert_anti_spam():
    """Same alert within 60 min should be suppressed."""
    _reset_health_state()
    stale = [{"agent_id": "zenya-test", "last_heartbeat": "2020-01-01T00:00:00Z", "status": "active"}]
    mock_sb = _make_mock_sb(stale_agents=stale)

    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
        with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
            mock_settings.mauro_whatsapp = "5512999999999"
            with patch("runtime.tasks.handlers.health_alert.send_text", create=True):
                # First call sends
                result1 = await handle_health_alert({})

    assert "enviado" in result1["message"].lower() or len(result1["alerts"]) > 0

    # Second call with same alerts should suppress
    mock_sb2 = _make_mock_sb(stale_agents=stale)
    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb2):
        with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
            mock_settings.mauro_whatsapp = "5512999999999"
            result2 = await handle_health_alert({})

    assert result2.get("suppressed") is True


@pytest.mark.asyncio
async def test_health_alert_consecutive_failures_escalation():
    """After 3 consecutive checks with alerts, escalate to critical."""
    _reset_health_state()
    stale = [{"agent_id": "test", "last_heartbeat": "2020-01-01T00:00:00Z", "status": "active"}]

    for i in range(3):
        # Reset anti-spam each time to force fresh alert
        health_alert_mod._last_alert_hash = ""
        health_alert_mod._last_alert_time = None

        mock_sb = _make_mock_sb(stale_agents=stale)
        with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
            with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
                mock_settings.mauro_whatsapp = ""
                result = await handle_health_alert({})

    # After 3 consecutive failures, should have critical alert
    assert any("CRÍTICO" in a or "critico" in a.lower() for a in result["alerts"])


@pytest.mark.asyncio
async def test_health_alert_rpc_fallback():
    """When RPC fails, falls back to table query for stale agents."""
    _reset_health_state()
    stale = [
        {
            "agent_id": "zenya-fallback",
            "last_heartbeat": (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat(),
            "status": "active",
        }
    ]
    mock_sb = _make_mock_sb(stale_agents=stale, rpc_raises=True)

    with patch("runtime.tasks.handlers.health_alert.supabase", mock_sb):
        with patch("runtime.tasks.handlers.health_alert.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            result = await handle_health_alert({})

    # Should still detect stale agents via fallback
    assert any("heartbeat" in a.lower() for a in result["alerts"])
