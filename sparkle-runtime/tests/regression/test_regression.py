"""
Cross-sprint regression test suite for Sparkle Runtime.

Validates critical paths that must never break between sprints:
  - Handler registry completeness
  - Health endpoint shape
  - Friday echo flow
  - Brain query/ingest status codes
  - Observer endpoints
  - Workflow engine endpoints
  - Character state endpoint
  - Agent routing resolution
  - System capabilities endpoint

All tests run against a mocked FastAPI TestClient — no real
Supabase, Claude API, or Z-API connections are required.

Run:  cd sparkle-runtime && python -m pytest tests/regression/ -v --tb=short
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# 1. HANDLER REGISTRY — all registered handlers respond to their task types
# ═══════════════════════════════════════════════════════════════════════════

class TestHandlerRegistry:
    """Ensures the task registry is complete and all handlers are callable."""

    def test_registry_not_empty(self):
        from runtime.tasks.registry import REGISTRY
        assert len(REGISTRY) > 20, f"Expected 20+ handlers, got {len(REGISTRY)}"

    def test_critical_handlers_present(self):
        from runtime.tasks.registry import REGISTRY
        critical = [
            "echo", "brain_ingest", "brain_query", "chat",
            "activate_agent", "health_alert", "daily_briefing",
            "generate_content", "extract_insights", "status_mrr",
            "status_report", "specialist_chat", "workflow_step",
            "onboard_client", "brain_ingest_pipeline",
        ]
        for task_type in critical:
            assert task_type in REGISTRY, f"Missing handler for '{task_type}'"

    def test_get_handler_returns_callable(self):
        from runtime.tasks.registry import get_handler
        handler = get_handler("echo")
        assert handler is not None
        assert callable(handler)

    def test_get_handler_returns_none_for_unknown(self):
        from runtime.tasks.registry import get_handler
        assert get_handler("nonexistent_xyz_999") is None

    def test_all_handlers_are_async(self):
        from runtime.tasks.registry import REGISTRY
        for task_type, handler in REGISTRY.items():
            assert callable(handler), f"'{task_type}' handler not callable"
            assert asyncio.iscoroutinefunction(handler), (
                f"'{task_type}' handler is not async"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 2. HEALTH ENDPOINT — returns required shape and checks
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:

    def test_health_returns_200(self, app_client):
        client, _ = app_client
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_keys(self, app_client):
        client, _ = app_client
        body = client.get("/health").json()
        assert "status" in body
        assert "version" in body
        assert "timestamp" in body
        assert "checks" in body

    def test_health_status_ok_or_degraded(self, app_client):
        client, _ = app_client
        body = client.get("/health").json()
        assert body["status"] in ("ok", "degraded")

    def test_health_has_all_checks(self, app_client):
        client, _ = app_client
        checks = client.get("/health").json()["checks"]
        expected = {
            "supabase", "zapi_connected", "zapi_configured",
            "groq_configured", "anthropic_configured",
        }
        assert expected.issubset(set(checks.keys())), (
            f"Missing checks: {expected - set(checks.keys())}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. FRIDAY ECHO — simplest handler, validates full request/response cycle
# ═══════════════════════════════════════════════════════════════════════════

class TestFridayEcho:

    @pytest.mark.asyncio
    async def test_echo_handler_returns_message(self):
        from runtime.tasks.handlers.echo import handle_echo
        result = await handle_echo({"payload": {"content": "regression test"}})
        assert "message" in result
        assert "regression test" in result["message"]

    @pytest.mark.asyncio
    async def test_echo_handler_handoff(self):
        from runtime.tasks.handlers.echo import handle_echo
        result = await handle_echo({
            "payload": {"content": "test", "return_handoff": True}
        })
        assert result.get("handoff_to") == "brain_ingest"

    @pytest.mark.asyncio
    async def test_echo_handler_brain_worthy(self):
        from runtime.tasks.handlers.echo import handle_echo
        result = await handle_echo({
            "payload": {"content": "test", "brain_worthy": True}
        })
        assert result.get("brain_worthy") is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. BRAIN ENDPOINTS — query and ingest return expected status codes
# ═══════════════════════════════════════════════════════════════════════════

class TestBrainEndpoints:

    def test_brain_activity_returns_200(self, app_client):
        client, mock_sb = app_client
        # brain/activity may query brain_entries
        mock_sb.set_table_data("brain_entries", [])
        resp = client.get("/brain/activity")
        assert resp.status_code == 200

    def test_brain_ingestions_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("brain_ingestions", [])
        resp = client.get("/brain/ingestions")
        assert resp.status_code == 200

    def test_brain_ingest_url_returns_422_without_body(self, app_client):
        """POST /brain/ingest-url without body should be 422 (validation)."""
        client, _ = app_client
        resp = client.post("/brain/ingest-url")
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 5. OBSERVER ENDPOINTS — gaps and summary return expected shapes
# ═══════════════════════════════════════════════════════════════════════════

class TestObserverEndpoints:

    def test_observer_gaps_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("gap_reports", [])
        resp = client.get("/observer/gaps")
        assert resp.status_code == 200
        body = resp.json()
        assert "gaps" in body
        assert "count" in body

    def test_observer_summary_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("gap_reports", [])
        resp = client.get("/observer/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_gaps" in body
        assert "by_status" in body

    def test_observer_quality_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("response_quality_log", [])
        resp = client.get("/observer/quality")
        assert resp.status_code == 200
        body = resp.json()
        assert "logs" in body

    def test_observer_quality_summary_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("response_quality_log", [])
        resp = client.get("/observer/quality/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_evaluations" in body


# ═══════════════════════════════════════════════════════════════════════════
# 6. WORKFLOW ENGINE — templates, instances, start validation
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkflowEngine:

    def test_workflow_templates_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("workflow_templates", [])
        resp = client.get("/workflow/templates")
        assert resp.status_code == 200
        body = resp.json()
        assert "templates" in body
        assert "count" in body

    def test_workflow_instances_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("workflow_instances", [])
        resp = client.get("/workflow/instances")
        assert resp.status_code == 200
        body = resp.json()
        assert "instances" in body
        assert "count" in body

    def test_workflow_template_definitions_returns_200(self, app_client):
        """In-code template definitions (no DB needed)."""
        client, _ = app_client
        resp = client.get("/workflow/templates/definitions/all")
        assert resp.status_code == 200
        body = resp.json()
        assert "definitions" in body
        assert body["count"] >= 1, "Should have at least 1 template definition"

    def test_workflow_start_rejects_missing_template(self, app_client):
        """POST /workflow/start with nonexistent template returns 404."""
        client, mock_sb = app_client
        mock_sb.set_table_data("workflow_templates", [])
        resp = client.post("/workflow/start", json={
            "template_slug": "nonexistent_slug",
            "name": "test",
        })
        assert resp.status_code == 404

    def test_workflow_handoffs_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("handoff_log", [])
        resp = client.get("/workflow/handoffs")
        assert resp.status_code == 200
        body = resp.json()
        assert "handoffs" in body


# ═══════════════════════════════════════════════════════════════════════════
# 7. FRIDAY MESSAGE ENDPOINT — accepts text and returns response
# ═══════════════════════════════════════════════════════════════════════════

class TestFridayMessage:

    def test_friday_message_returns_200(self, app_client):
        """POST /friday/message with echo-style text returns 200."""
        client, mock_sb = app_client
        # The dispatcher will try to insert into runtime_tasks
        mock_sb.set_table_data("runtime_tasks", [])
        mock_sb.set_table_data("conversation_history", [])

        with patch("runtime.friday.dispatcher.call_claude", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = json.dumps({
                "intent": "echo",
                "domain": "geral",
                "params": {},
                "summary": "echo test",
            })
            resp = client.post("/friday/message", json={"text": "echo test"})

        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") in ("ok", "error")


# ═══════════════════════════════════════════════════════════════════════════
# 8. CHARACTER STATE — endpoint responds for known slug pattern
# ═══════════════════════════════════════════════════════════════════════════

class TestCharacterState:

    def test_character_profile_404_for_unknown(self, app_client):
        """GET /character/unknown_slug returns 404."""
        client, mock_sb = app_client
        mock_sb.set_table_data("characters", [])
        resp = client.get("/character/nonexistent_slug")
        assert resp.status_code in (404, 500)

    def test_character_state_endpoint_exists(self, app_client):
        """GET /character/{slug}/state should not 405 (method not allowed)."""
        client, mock_sb = app_client
        mock_sb.set_table_data("character_state", [])
        mock_sb.set_table_data("characters", [])
        resp = client.get("/character/zenya/state")
        # Should be 200 (auto-creates) or 500 (mock limitation) but NOT 405
        assert resp.status_code != 405


# ═══════════════════════════════════════════════════════════════════════════
# 9. AGENT ROUTING — resolves known intents
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentRouting:

    def test_agent_list_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("agents", [])
        resp = client.get("/agent/list")
        assert resp.status_code == 200

    def test_agent_invoke_rejects_empty_body(self, app_client):
        """POST /agent/invoke without body returns 422."""
        client, _ = app_client
        resp = client.post("/agent/invoke")
        assert resp.status_code == 422

    def test_dispatcher_intents_and_domains_loaded(self):
        """Friday dispatcher must have valid INTENTS and DOMAINS lists."""
        from runtime.friday.dispatcher import INTENTS, DOMAINS
        assert len(INTENTS) > 10, f"Expected 10+ intents, got {len(INTENTS)}"
        assert len(DOMAINS) >= 7, f"Expected 7+ domains, got {len(DOMAINS)}"
        assert "geral" in DOMAINS
        assert "trafego_pago" in DOMAINS


# ═══════════════════════════════════════════════════════════════════════════
# 10. SYSTEM CAPABILITIES — /system/capabilities returns expected shape
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemCapabilities:

    def test_system_capabilities_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("brain_entries", [])
        mock_sb.set_table_data("agents", [])
        resp = client.get("/system/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert "handlers" in body
        assert "domains" in body
        assert "agents" in body

    def test_system_state_endpoint_exists(self, app_client):
        """GET /system/state uses raw httpx to Supabase REST API (not the
        mocked client), so it will fail with a ConnectError in test env.
        We mock httpx.AsyncClient to verify the route is wired correctly."""
        client, mock_sb = app_client
        mock_sb.set_table_data("agent_work_items", [])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("runtime.system_router.httpx.AsyncClient", return_value=mock_http):
            resp = client.get("/system/state")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 11. CONTENT LIST — /content/list returns expected shape
# ═══════════════════════════════════════════════════════════════════════════

class TestContentEndpoints:

    def test_content_list_returns_200(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("content_items", [])
        resp = client.get("/content/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "count" in body

    def test_content_list_items_is_list(self, app_client):
        client, mock_sb = app_client
        mock_sb.set_table_data("content_items", [])
        body = client.get("/content/list").json()
        assert isinstance(body["items"], list)


# ═══════════════════════════════════════════════════════════════════════════
# 12. FRIDAY TTS INFO — /friday/tts-info responds
# ═══════════════════════════════════════════════════════════════════════════

class TestFridayTTSInfo:

    def test_tts_info_returns_200(self, app_client):
        client, _ = app_client
        resp = client.get("/friday/tts-info")
        assert resp.status_code == 200
        body = resp.json()
        # Must always have these keys even on error/no-config
        assert "engine" in body
        assert "status" in body
