"""
Smoke tests for Sparkle Runtime.

Validates that all critical endpoints respond with 200 and expected shapes.
Run: pytest sparkle-runtime/tests/test_smoke.py -v
"""
from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.anyio


# ── Health ────────────────────────────────────────────────────

async def test_health_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    assert "checks" in body
    assert "timestamp" in body


async def test_health_has_required_checks(client: httpx.AsyncClient):
    resp = await client.get("/health")
    checks = resp.json()["checks"]
    expected_keys = {"supabase", "zapi_connected", "zapi_configured", "groq_configured", "anthropic_configured"}
    assert expected_keys.issubset(set(checks.keys()))


# ── Brain Activity ────────────────────────────────────────────

async def test_brain_activity_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/brain/activity")
    assert resp.status_code == 200
    body = resp.json()
    # Should have the dashboard structure
    assert "processing" in body or "status" in body
    if "status" not in body:  # normal success path
        assert "recent" in body
        assert "insights" in body
        assert "stats" in body


# ── Content List ──────────────────────────────────────────────

async def test_content_list_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/content/list")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "count" in body
    assert isinstance(body["items"], list)


# ── Friday Message ────────────────────────────────────────────

async def test_friday_echo_returns_200(client: httpx.AsyncClient):
    resp = await client.post("/friday/message", json={"text": "echo test"})
    assert resp.status_code == 200
    body = resp.json()
    # Friday message endpoint should return a response dict
    assert isinstance(body, dict)


# ── Workflow Template Definitions ─────────────────────────────

async def test_workflow_template_definitions_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/workflow/templates/definitions/all")
    assert resp.status_code == 200
    body = resp.json()
    assert "definitions" in body
    assert "count" in body
    assert body["count"] == 3, f"Expected 3 template definitions, got {body['count']}"


async def test_workflow_template_definitions_have_correct_slugs(client: httpx.AsyncClient):
    resp = await client.get("/workflow/templates/definitions/all")
    body = resp.json()
    slugs = {d["slug"] for d in body["definitions"]}
    expected = {"onboarding_zenya", "content_production", "brain_learning"}
    assert slugs == expected, f"Expected slugs {expected}, got {slugs}"


async def test_workflow_template_definitions_have_steps(client: httpx.AsyncClient):
    resp = await client.get("/workflow/templates/definitions/all")
    for defn in resp.json()["definitions"]:
        assert defn["total_steps"] > 0, f"Template '{defn['slug']}' has 0 steps"
        assert len(defn["steps_summary"]) == defn["total_steps"]
        for step in defn["steps_summary"]:
            assert "task_type" in step
            assert "name" in step


# ── Workflow Templates (DB) ───────────────────────────────────

async def test_workflow_templates_list_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/workflow/templates")
    assert resp.status_code == 200
    body = resp.json()
    assert "templates" in body
    assert "count" in body


# ── Brain Ingestions ──────────────────────────────────────────

async def test_brain_ingestions_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/brain/ingestions")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"


# ── Workflow Instances ────────────────────────────────────────

async def test_workflow_instances_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/workflow/instances")
    assert resp.status_code == 200
    body = resp.json()
    assert "instances" in body
    assert "count" in body
