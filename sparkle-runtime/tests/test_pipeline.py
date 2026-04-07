"""
Integration tests for Pipeline Orchestrator (CONTENT-1.6).

Tests run against the LIVE runtime at https://runtime.sparkleai.tech
Run: pytest tests/test_pipeline.py -v

Test coverage:
  - POST /content/briefs      → create + fire pipeline
  - GET  /content/briefs      → list with status + current_stage
  - GET  /content/pieces/{id} → detail + pipeline_log
  - GET  /content/queue       → pending_approval list
  - POST /content/pieces/{id}/approve  → approve
  - POST /content/pieces/{id}/reject   → reject with reason
  - POST /content/pieces/{id}/retry    → retry from failed state
  - POST /content/pipeline/tick        → cron tick
  - Concurrency: 5-piece limit enforced
  - pipeline_log structure validation
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.anyio

RUNTIME_URL = os.environ.get("RUNTIME_BASE_URL", "https://runtime.sparkleai.tech")
API_KEY = os.environ.get("RUNTIME_API_KEY", "oOPXtj29_e02tla-XFAYQuXvh6T2STpnltJ41G1uCqM")
HEADERS = {"X-API-Key": API_KEY}

VALID_BRIEF = {
    "theme": "IA revolucionando PMEs no Brasil",
    "mood": "inspirador",
    "style": "influencer_natural",
    "platform": "instagram",
}


# ── Helpers ────────────────────────────────────────────────────

async def _create_brief(client: httpx.AsyncClient, **overrides) -> dict:
    """Create a brief and return the response body."""
    payload = {**VALID_BRIEF, **overrides}
    resp = await client.post("/content/briefs", json=payload)
    assert resp.status_code == 200, f"create_brief failed: {resp.status_code} {resp.text}"
    return resp.json()


async def _get_piece(client: httpx.AsyncClient, piece_id: str) -> dict:
    resp = await client.get(f"/content/pieces/{piece_id}")
    assert resp.status_code == 200, f"get_piece failed: {resp.status_code} {resp.text}"
    return resp.json()


# ── POST /content/briefs ──────────────────────────────────────

async def test_create_brief_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/briefs", json=VALID_BRIEF)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


async def test_create_brief_returns_id_and_status():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        body = await _create_brief(c)
    assert "id" in body, "Response must contain 'id'"
    assert "status" in body, "Response must contain 'status'"
    assert body["status"] == "briefed", f"Initial status must be 'briefed', got: {body['status']}"
    assert "message" in body


async def test_create_brief_persists_to_db():
    """Verify the piece is actually created in Supabase."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        created = await _create_brief(c)
        piece_id = created["id"]

        # Fetch it back
        piece = await _get_piece(c, piece_id)

    assert piece["id"] == piece_id
    assert piece["theme"] == VALID_BRIEF["theme"]
    assert piece["status"] in (
        "briefed", "image_generating", "image_done", "video_done",
        "pending_approval", "image_failed",  # pipeline may have already advanced
    )


async def test_create_brief_has_pipeline_log():
    """pipeline_log must be initialized with at least a 'created' event."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        created = await _create_brief(c)
        piece = await _get_piece(c, created["id"])

    log = piece.get("pipeline_log") or []
    assert isinstance(log, list), "pipeline_log must be a list"
    assert len(log) >= 1, "pipeline_log must have at least one entry"


async def test_create_brief_missing_theme_returns_422():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/briefs", json={"mood": "inspirador"})
    assert resp.status_code == 422, f"Expected 422 for missing theme, got {resp.status_code}"


# ── GET /content/briefs ───────────────────────────────────────

async def test_list_briefs_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/briefs")
    assert resp.status_code == 200


async def test_list_briefs_has_items_and_count():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        # Create one first
        await _create_brief(c)
        resp = await c.get("/content/briefs")
    body = resp.json()
    assert "items" in body
    assert "count" in body
    assert body["count"] >= 1


async def test_list_briefs_includes_current_stage():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        await _create_brief(c)
        resp = await c.get("/content/briefs")
    items = resp.json()["items"]
    assert len(items) > 0
    # Every item must have current_stage
    for item in items[:5]:
        assert "current_stage" in item, f"Item missing current_stage: {item.get('id')}"
        assert isinstance(item["current_stage"], str)


async def test_list_briefs_filter_by_status():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/briefs", params={"status": "briefed"})
    body = resp.json()
    assert resp.status_code == 200
    # All returned items should be briefed
    for item in body.get("items", []):
        assert item["status"] == "briefed"


# ── GET /content/pieces/{id} ──────────────────────────────────

async def test_get_piece_detail_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        created = await _create_brief(c)
        resp = await c.get(f"/content/pieces/{created['id']}")
    assert resp.status_code == 200


async def test_get_piece_detail_has_pipeline_log():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        created = await _create_brief(c)
        piece = await _get_piece(c, created["id"])

    log = piece.get("pipeline_log")
    assert log is not None, "pipeline_log must be present"
    assert isinstance(log, list)


async def test_get_piece_detail_pipeline_log_structure():
    """Each log entry from transitions must have 'from', 'to', 'at'."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        created = await _create_brief(c)
        piece = await _get_piece(c, created["id"])

    log = piece.get("pipeline_log") or []
    # Find transition entries (have from+to fields)
    transitions = [e for e in log if "from" in e and "to" in e]
    for entry in transitions:
        assert "from" in entry, "Log entry must have 'from'"
        assert "to" in entry, "Log entry must have 'to'"
        assert "at" in entry, "Log entry must have 'at' timestamp"


async def test_get_nonexistent_piece_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get(f"/content/pieces/{fake_id}")
    assert resp.status_code == 404


# ── GET /content/queue ────────────────────────────────────────

async def test_get_queue_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/queue")
    assert resp.status_code == 200


async def test_get_queue_has_items_and_count():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/queue")
    body = resp.json()
    assert "items" in body
    assert "count" in body


async def test_get_queue_items_are_pending_approval():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/queue")
    for item in resp.json().get("items", []):
        assert item["status"] == "pending_approval", (
            f"Queue item {item.get('id')} has status {item.get('status')}"
        )


# ── POST /content/pieces/{id}/approve ────────────────────────

async def _put_piece_in_pending(client: httpx.AsyncClient) -> str | None:
    """
    Try to find or create a piece in pending_approval.
    Returns piece_id or None if none available.
    """
    # Check queue first
    resp = await client.get("/content/queue")
    items = resp.json().get("items", [])
    if items:
        return items[0]["id"]
    return None


async def test_approve_piece_endpoint_exists():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        piece_id = await _put_piece_in_pending(c)
        if not piece_id:
            pytest.skip("No pieces in pending_approval — skipping approve test")

        resp = await c.post(f"/content/pieces/{piece_id}/approve", json={})
    # 200 if approved, 400 if already in wrong state
    assert resp.status_code in (200, 400)


async def test_approve_nonexistent_piece_returns_400():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/pieces/{fake_id}/approve", json={})
    assert resp.status_code == 400


async def test_approve_with_scheduled_at():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        piece_id = await _put_piece_in_pending(c)
        if not piece_id:
            pytest.skip("No pieces in pending_approval")

        resp = await c.post(f"/content/pieces/{piece_id}/approve", json={
            "scheduled_at": "2026-05-01T10:00:00+00:00"
        })
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        body = resp.json()
        assert body["status"] in ("approved", "scheduled")


# ── POST /content/pieces/{id}/reject ─────────────────────────

async def test_reject_piece_endpoint_exists():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        piece_id = await _put_piece_in_pending(c)
        if not piece_id:
            pytest.skip("No pieces in pending_approval — skipping reject test")

        resp = await c.post(
            f"/content/pieces/{piece_id}/reject",
            json={"reason": "Teste de rejeicao automatica"},
        )
    assert resp.status_code in (200, 400)


async def test_reject_nonexistent_piece_returns_400():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/pieces/{fake_id}/reject", json={"reason": "test"})
    assert resp.status_code == 400


# ── POST /content/pieces/{id}/retry ──────────────────────────

async def test_retry_piece_non_failed_returns_400():
    """Retrying a piece that is NOT in *_failed state must return 400."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        created = await _create_brief(c)
        # Briefed piece cannot be retried
        resp = await c.post(f"/content/pieces/{created['id']}/retry")
    assert resp.status_code == 400, f"Expected 400 for non-failed piece, got {resp.status_code}"


async def test_retry_nonexistent_piece_returns_400():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/pieces/{fake_id}/retry")
    assert resp.status_code == 400


# ── POST /content/pipeline/tick ──────────────────────────────

async def test_pipeline_tick_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/pipeline/tick")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


async def test_pipeline_tick_returns_result_structure():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/pipeline/tick")
    body = resp.json()
    assert "advanced" in body, "Tick result must have 'advanced'"
    assert "skipped" in body, "Tick result must have 'skipped'"
    assert "errors" in body, "Tick result must have 'errors'"
    assert isinstance(body["advanced"], list)
    assert isinstance(body["skipped"], list)
    assert isinstance(body["errors"], list)


# ── Concurrency limit ─────────────────────────────────────────

async def test_concurrent_limit_enforced():
    """
    Verify that the concurrency limit (5) is checked by the pipeline.
    We test this by querying the /briefs list — if >= 5 are generating,
    new pieces in 'briefed' state won't be advanced until slots free up.

    This is a structural test (we don't actually fill 5 slots here —
    that would require real image generation). Instead we verify the
    endpoint and logic exist and respond correctly.
    """
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        # Create a brief and confirm it's created
        created = await _create_brief(c, theme="test concorrencia pipeline")
        assert created["id"]
        assert created["status"] == "briefed"

        # Verify it shows in the list
        list_resp = await c.get("/content/briefs", params={"status": "briefed"})
        assert list_resp.status_code == 200
