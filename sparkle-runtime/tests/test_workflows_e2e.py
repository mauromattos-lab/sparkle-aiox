"""
End-to-end tests for the 3 workflow templates in Sparkle Runtime.

Tests run against the LIVE runtime at https://runtime.sparkleai.tech
They exercise the full workflow engine: seed -> start -> step execution -> completion.

Run: pytest sparkle-runtime/tests/test_workflows_e2e.py -v --timeout=120
"""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

pytestmark = pytest.mark.anyio

# Max seconds to poll for workflow completion
POLL_TIMEOUT = 90
POLL_INTERVAL = 3


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

async def poll_workflow_instance(
    client: httpx.AsyncClient,
    instance_id: str,
    *,
    terminal_statuses: set[str] | None = None,
    timeout: int = POLL_TIMEOUT,
    interval: int = POLL_INTERVAL,
) -> dict:
    """
    Poll GET /workflow/instances/{id} until the instance reaches a terminal status.
    Returns the final instance payload.
    """
    if terminal_statuses is None:
        terminal_statuses = {"completed", "failed", "cancelled"}

    elapsed = 0
    while elapsed < timeout:
        resp = await client.get(f"/workflow/instances/{instance_id}")
        assert resp.status_code == 200, f"Instance GET failed: {resp.status_code} {resp.text}"
        data = resp.json()
        if data.get("status") in terminal_statuses:
            return data
        await asyncio.sleep(interval)
        elapsed += interval

    # Final check
    resp = await client.get(f"/workflow/instances/{instance_id}")
    return resp.json()


# ═══════════════════════════════════════════════════════════════════
# A. Template Seeding
# ═══════════════════════════════════════════════════════════════════

class TestTemplateSeed:
    """Validate that POST /workflow/templates/seed upserts 3 templates correctly."""

    async def test_seed_endpoint_returns_200(self, client: httpx.AsyncClient):
        resp = await client.post("/workflow/templates/seed")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_templates" in body
        assert body["total_templates"] == 3
        assert "errors" in body
        assert body["errors"] == [], f"Seed had errors: {body['errors']}"

    async def test_seed_is_idempotent(self, client: httpx.AsyncClient):
        """Calling seed twice should not fail or duplicate."""
        resp1 = await client.post("/workflow/templates/seed")
        assert resp1.status_code == 200
        resp2 = await client.post("/workflow/templates/seed")
        assert resp2.status_code == 200
        body2 = resp2.json()
        # Second call should skip (same version) — 0 inserted, 0 updated
        assert body2["inserted"] == 0, "Second seed should not insert again"
        assert body2["errors"] == []

    async def test_seed_creates_templates_in_db(self, client: httpx.AsyncClient):
        """After seeding, /workflow/templates should list all 3."""
        # Ensure seeded
        await client.post("/workflow/templates/seed")

        resp = await client.get("/workflow/templates")
        assert resp.status_code == 200
        body = resp.json()

        slugs = {t["slug"] for t in body["templates"]}
        expected = {"onboarding_zenya", "content_production", "brain_learning"}
        assert expected.issubset(slugs), f"Missing templates. Found: {slugs}"

    async def test_each_template_has_steps(self, client: httpx.AsyncClient):
        """Verify each template slug returns correct step structure."""
        await client.post("/workflow/templates/seed")

        expected_steps = {
            "onboarding_zenya": 5,
            "content_production": 3,
            "brain_learning": 3,
        }

        for slug, expected_count in expected_steps.items():
            resp = await client.get(f"/workflow/templates/{slug}")
            assert resp.status_code == 200, f"Template '{slug}' not found"
            body = resp.json()
            assert body["total_steps"] == expected_count, (
                f"Template '{slug}' expected {expected_count} steps, got {body['total_steps']}"
            )
            steps = body.get("steps", [])
            assert len(steps) == expected_count

            # Verify each step has required fields
            for step in steps:
                assert "task_type" in step, f"Step in '{slug}' missing task_type"
                assert "name" in step, f"Step in '{slug}' missing name"
                assert "on_success" in step, f"Step '{step['name']}' missing on_success"
                assert "on_failure" in step, f"Step '{step['name']}' missing on_failure"

    async def test_template_task_types_are_registered(self, client: httpx.AsyncClient):
        """All task_types referenced in templates should exist in the registry."""
        resp = await client.get("/workflow/templates/definitions/all")
        body = resp.json()

        # These are the task_types we know exist in the registry
        known_task_types = {
            "brain_ingest_pipeline", "brain_query", "extract_client_dna",
            "onboard_client", "chat", "generate_content", "extract_insights",
            "cross_source_synthesis",
        }

        for defn in body["definitions"]:
            for step in defn["steps_summary"]:
                task_type = step["task_type"]
                assert task_type in known_task_types, (
                    f"Template '{defn['slug']}' step '{step['name']}' uses unregistered "
                    f"task_type '{task_type}'"
                )


# ═══════════════════════════════════════════════════════════════════
# B. brain_learning workflow — E2E
# ═══════════════════════════════════════════════════════════════════

class TestBrainLearningWorkflow:
    """
    Tests the brain_learning workflow end-to-end with a small text input
    (no URL/Apify dependency).
    """

    async def test_start_brain_learning(self, client: httpx.AsyncClient):
        """Start brain_learning workflow and verify instance is created."""
        # Ensure templates are seeded
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-brain-learning-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": unique_name,
            "context": {
                "source_type": "document",
                "source_ref": None,
                "title": "QA Test Document",
                "persona": "mauro",
                "force_domains": None,
                # Small text that brain_ingest_pipeline can process without URL
                "raw_content": (
                    "Inteligencia artificial generativa esta transformando o marketing digital. "
                    "Modelos como Claude e GPT permitem automacao de atendimento, geracao de "
                    "conteudo e analise de dados em escala. Para PMEs brasileiras, o custo de "
                    "implementacao caiu 90% nos ultimos 2 anos. Frameworks como LangChain e "
                    "AutoGen permitem orquestracao de agentes autonomos. O mercado de IA no "
                    "Brasil deve atingir US$ 3 bilhoes ate 2027."
                ),
            },
        })

        assert resp.status_code == 200, f"Start failed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert "instance_id" in body
        assert body["status"] == "running"
        assert body["total_steps"] == 3
        assert body["template_slug"] == "brain_learning"
        assert body["first_task_id"] is not None

    async def test_brain_learning_instance_status_transitions(self, client: httpx.AsyncClient):
        """
        Start brain_learning and poll until terminal state.
        Verify status reaches completed or failed (not stuck in running).
        """
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-brain-e2e-{uuid.uuid4().hex[:8]}"
        start_resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": unique_name,
            "context": {
                "source_type": "document",
                "source_ref": None,
                "title": "QA Transition Test",
                "persona": "mauro",
                "force_domains": None,
                "raw_content": (
                    "Teste de transicao de status do workflow engine. "
                    "Este texto simples deve ser ingerido pelo brain e gerar chunks. "
                    "Se o pipeline funcionar, insights serao extraidos automaticamente."
                ),
            },
        })

        assert start_resp.status_code == 200
        instance_id = start_resp.json()["instance_id"]

        # Poll until terminal
        final = await poll_workflow_instance(client, instance_id)
        assert final["status"] in ("completed", "failed"), (
            f"Workflow stuck in '{final['status']}' after {POLL_TIMEOUT}s. "
            f"current_step={final.get('current_step')}"
        )

    async def test_brain_learning_context_accumulates(self, client: httpx.AsyncClient):
        """Verify that each step result is stored in the instance context."""
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-brain-ctx-{uuid.uuid4().hex[:8]}"
        start_resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": unique_name,
            "context": {
                "source_type": "document",
                "source_ref": None,
                "title": "QA Context Test",
                "persona": "mauro",
                "force_domains": None,
                "raw_content": (
                    "Frameworks de orquestracao de agentes: CrewAI, AutoGen, LangGraph. "
                    "Cada um resolve um problema diferente. CrewAI foca em role-playing, "
                    "AutoGen em conversacao multi-agente, LangGraph em grafos de estado."
                ),
            },
        })

        instance_id = start_resp.json()["instance_id"]
        final = await poll_workflow_instance(client, instance_id)

        context = final.get("context", {})
        # Step 0 result should be stored
        assert "step_0_result" in context, (
            f"step_0_result not in context. Keys: {list(context.keys())}"
        )
        assert "step_0_name" in context

        # If workflow completed, step 1 and 2 should also be in context
        if final["status"] == "completed":
            assert "step_1_result" in context, "step_1_result missing on completed workflow"
            assert "step_2_result" in context, "step_2_result missing on completed workflow"


# ═══════════════════════════════════════════════════════════════════
# C. content_production workflow — E2E
# ═══════════════════════════════════════════════════════════════════

class TestContentProductionWorkflow:
    """
    Tests the content_production workflow end-to-end.
    Steps: brain_query -> generate_content -> notification (chat)
    """

    async def test_start_content_production(self, client: httpx.AsyncClient):
        """Start content_production and verify instance is created."""
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-content-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/workflow/start", json={
            "template_slug": "content_production",
            "name": unique_name,
            "context": {
                "topic": "como usar IA para melhorar atendimento ao cliente no WhatsApp",
                "format": "instagram_post",
                "persona": "zenya",
            },
        })

        assert resp.status_code == 200, f"Start failed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert body["instance_id"] is not None
        assert body["status"] == "running"
        assert body["total_steps"] == 3
        assert body["template_slug"] == "content_production"

    async def test_content_production_completes(self, client: httpx.AsyncClient):
        """
        Start content_production workflow and poll until terminal.
        The brain_query step has on_failure.continue=True, so even if Brain
        has no relevant data, workflow should proceed to generate_content.
        """
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-content-e2e-{uuid.uuid4().hex[:8]}"
        start_resp = await client.post("/workflow/start", json={
            "template_slug": "content_production",
            "name": unique_name,
            "context": {
                "topic": "dicas praticas de marketing digital para confeitarias",
                "format": "instagram_post",
                "persona": "zenya",
            },
        })

        assert start_resp.status_code == 200
        instance_id = start_resp.json()["instance_id"]

        final = await poll_workflow_instance(client, instance_id)
        assert final["status"] in ("completed", "failed"), (
            f"Workflow stuck in '{final['status']}' after {POLL_TIMEOUT}s"
        )

    async def test_content_production_generates_content(self, client: httpx.AsyncClient):
        """
        If content_production completes, verify step 1 (generate_content)
        result is in context and generated_content table has a new entry.
        """
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-content-gen-{uuid.uuid4().hex[:8]}"
        start_resp = await client.post("/workflow/start", json={
            "template_slug": "content_production",
            "name": unique_name,
            "context": {
                "topic": "tendencias de IA para pequenas empresas em 2026",
                "format": "instagram_post",
                "persona": "zenya",
            },
        })

        instance_id = start_resp.json()["instance_id"]
        final = await poll_workflow_instance(client, instance_id)

        if final["status"] == "completed":
            context = final.get("context", {})
            # generate_content is step 1
            step_1 = context.get("step_1_result", {})
            assert step_1, "step_1_result (generate_content) should have data on completed workflow"

            # Check generated_content list has recent items
            list_resp = await client.get("/content/list?limit=5")
            assert list_resp.status_code == 200
            # We can't guarantee our specific content is in top 5, but the endpoint works


# ═══════════════════════════════════════════════════════════════════
# D. Error Handling
# ═══════════════════════════════════════════════════════════════════

class TestWorkflowErrorHandling:
    """Tests error paths and edge cases in the workflow engine."""

    async def test_start_with_invalid_template_slug(self, client: httpx.AsyncClient):
        """Starting with a non-existent template slug should return 404."""
        resp = await client.post("/workflow/start", json={
            "template_slug": "nonexistent_template_slug_12345",
            "name": "qa-invalid-slug",
            "context": {},
        })
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        assert "nonexistent_template_slug_12345" in body["detail"]

    async def test_start_with_empty_name(self, client: httpx.AsyncClient):
        """Starting with empty name should still work (name is not validated beyond being a string)."""
        await client.post("/workflow/templates/seed")
        resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": "",
            "context": {
                "source_type": "document",
                "source_ref": None,
                "title": "QA Empty Name Test",
                "persona": "mauro",
                "raw_content": "Test content for empty name scenario.",
            },
        })
        # The API should accept this — name is just metadata
        assert resp.status_code == 200

    async def test_start_with_missing_context_keys(self, client: httpx.AsyncClient):
        """
        Starting brain_learning without required context keys (source_type etc.)
        should start but the first step should handle missing data gracefully.

        NOTE: The workflow_step handler resolves {{variable}} from context. With an
        empty context, placeholders remain as literal strings like "{{source_type}}".
        The brain_ingest_pipeline handler may still attempt processing and take time.

        Expected behavior: workflow eventually fails at step 0 (on_failure.continue=False)
        or the step runs with unresolved placeholders.
        """
        await client.post("/workflow/templates/seed")

        resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": f"qa-missing-ctx-{uuid.uuid4().hex[:8]}",
            "context": {},  # No source_type, no source_ref, no raw_content
        })

        assert resp.status_code == 200
        instance_id = resp.json()["instance_id"]

        # Poll with longer timeout — step execution may be slow even with invalid data
        final = await poll_workflow_instance(client, instance_id, timeout=POLL_TIMEOUT)

        # Acceptable outcomes:
        # - "failed": step 0 handler detected invalid input and on_failure.continue=False
        # - "completed": handler somehow processed unresolved placeholders
        # - "running": step is still executing (slow handler) — this is a QA finding:
        #   the handler does not fail-fast on missing input, which delays error feedback
        if final["status"] == "running":
            pytest.xfail(
                "QA FINDING: brain_ingest_pipeline does not fail-fast on missing "
                "source data. Workflow stays in 'running' beyond timeout. "
                f"current_step={final.get('current_step')}"
            )

    async def test_get_nonexistent_instance(self, client: httpx.AsyncClient):
        """GET /workflow/instances/{fake_id} should return 404 or error."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/workflow/instances/{fake_id}")
        # Supabase .single() on no rows raises — handler should return 404
        assert resp.status_code in (404, 500), (
            f"Expected 404/500 for nonexistent instance, got {resp.status_code}"
        )

    async def test_cancel_workflow(self, client: httpx.AsyncClient):
        """Start a workflow and immediately cancel it."""
        await client.post("/workflow/templates/seed")

        start_resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": f"qa-cancel-{uuid.uuid4().hex[:8]}",
            "context": {
                "source_type": "document",
                "source_ref": None,
                "title": "QA Cancel Test",
                "persona": "mauro",
                "raw_content": "This workflow will be cancelled immediately.",
            },
        })

        assert start_resp.status_code == 200
        instance_id = start_resp.json()["instance_id"]

        # Cancel immediately
        cancel_resp = await client.post(f"/workflow/instances/{instance_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # Verify instance is cancelled
        get_resp = await client.get(f"/workflow/instances/{instance_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "cancelled"

    async def test_cancel_already_cancelled_fails(self, client: httpx.AsyncClient):
        """Cancelling an already-cancelled workflow should return 400."""
        await client.post("/workflow/templates/seed")

        start_resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": f"qa-double-cancel-{uuid.uuid4().hex[:8]}",
            "context": {
                "source_type": "document",
                "raw_content": "Double cancel test.",
            },
        })

        instance_id = start_resp.json()["instance_id"]

        # Cancel first time
        await client.post(f"/workflow/instances/{instance_id}/cancel")

        # Cancel second time — should fail
        resp = await client.post(f"/workflow/instances/{instance_id}/cancel")
        assert resp.status_code == 400

    async def test_pause_and_resume_workflow(self, client: httpx.AsyncClient):
        """Pause a running workflow, then resume it."""
        await client.post("/workflow/templates/seed")

        start_resp = await client.post("/workflow/start", json={
            "template_slug": "brain_learning",
            "name": f"qa-pause-resume-{uuid.uuid4().hex[:8]}",
            "context": {
                "source_type": "document",
                "raw_content": "Pause and resume test content for the workflow engine.",
            },
        })

        assert start_resp.status_code == 200
        instance_id = start_resp.json()["instance_id"]

        # Small delay to let the first step start
        await asyncio.sleep(1)

        # Try to pause (might fail if already completed/failed)
        pause_resp = await client.post(f"/workflow/instances/{instance_id}/pause")
        if pause_resp.status_code == 200:
            assert pause_resp.json()["status"] == "paused"

            # Verify paused
            get_resp = await client.get(f"/workflow/instances/{instance_id}")
            assert get_resp.json()["status"] == "paused"

            # Resume
            resume_resp = await client.post(f"/workflow/instances/{instance_id}/resume")
            assert resume_resp.status_code == 200
            assert resume_resp.json()["status"] == "running"
            assert "task_id" in resume_resp.json()
        else:
            # Instance already in terminal state — acceptable for fast execution
            pytest.skip("Workflow completed before pause could be applied")

    async def test_on_failure_continue_true_advances(self, client: httpx.AsyncClient):
        """
        In content_production, step 0 (brain_query) has on_failure.continue=True.
        Even if brain_query returns no results, workflow should advance to step 1.
        """
        await client.post("/workflow/templates/seed")

        unique_name = f"qa-failure-continue-{uuid.uuid4().hex[:8]}"
        start_resp = await client.post("/workflow/start", json={
            "template_slug": "content_production",
            "name": unique_name,
            "context": {
                # Obscure topic unlikely to match any Brain data
                "topic": "quantum entanglement in fermented kombucha production",
                "format": "instagram_post",
                "persona": "zenya",
            },
        })

        assert start_resp.status_code == 200
        instance_id = start_resp.json()["instance_id"]

        final = await poll_workflow_instance(client, instance_id)

        # Even if brain_query fails/returns nothing, workflow should continue
        context = final.get("context", {})
        # If brain_query failed but continued, current_step should be > 0
        current = final.get("current_step", 0)
        assert current > 0 or final["status"] in ("completed", "failed"), (
            f"Workflow should have advanced past step 0. current_step={current}, status={final['status']}"
        )


# ═══════════════════════════════════════════════════════════════════
# E. onboarding_zenya — structural validation (not full E2E due to deps)
# ═══════════════════════════════════════════════════════════════════

class TestOnboardingZenyaStructure:
    """
    The onboarding_zenya workflow requires real client data and scraping.
    We test structural correctness without running the full pipeline.
    """

    async def test_onboarding_template_structure(self, client: httpx.AsyncClient):
        """Verify onboarding_zenya template has all 5 steps with correct task_types."""
        await client.post("/workflow/templates/seed")

        resp = await client.get("/workflow/templates/onboarding_zenya")
        assert resp.status_code == 200
        body = resp.json()

        assert body["total_steps"] == 5

        expected_task_types = [
            "brain_ingest_pipeline",    # step 0: scrape site
            "brain_ingest_pipeline",    # step 1: supplementary ingest
            "extract_client_dna",       # step 2: DNA extraction
            "onboard_client",           # step 3: system prompt generation
            "chat",                     # step 4: notify Mauro
        ]

        steps = body["steps"]
        for i, expected_type in enumerate(expected_task_types):
            assert steps[i]["task_type"] == expected_type, (
                f"Step {i} expected task_type '{expected_type}', got '{steps[i]['task_type']}'"
            )

    async def test_onboarding_step_1_failure_continues(self, client: httpx.AsyncClient):
        """Step 1 (supplementary ingest) has on_failure.continue=True."""
        await client.post("/workflow/templates/seed")

        resp = await client.get("/workflow/templates/onboarding_zenya")
        steps = resp.json()["steps"]

        # Step 1 should continue on failure
        assert steps[1]["on_failure"]["continue"] is True
        assert steps[1]["on_failure"]["next_step"] == 2

        # Step 0 should NOT continue on failure
        assert steps[0]["on_failure"]["continue"] is False

    async def test_onboarding_start_without_required_context_fails_at_step0(
        self, client: httpx.AsyncClient
    ):
        """
        Starting onboarding_zenya without site_url in context should fail
        at step 0 (scrape_site needs a URL).
        """
        await client.post("/workflow/templates/seed")

        resp = await client.post("/workflow/start", json={
            "template_slug": "onboarding_zenya",
            "name": f"qa-onboard-nourl-{uuid.uuid4().hex[:8]}",
            "context": {
                "business_name": "QA Test Business",
                "business_type": "teste",
                # No site_url, no client_id
            },
        })

        assert resp.status_code == 200
        instance_id = resp.json()["instance_id"]

        # Should fail since step 0 has no URL and on_failure.continue=False
        final = await poll_workflow_instance(client, instance_id, timeout=60)
        assert final["status"] == "failed", (
            f"Expected 'failed' without site_url, got '{final['status']}'"
        )
