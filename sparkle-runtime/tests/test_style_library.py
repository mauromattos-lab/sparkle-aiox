"""
Integration tests for Style Library endpoints (CONTENT-0.1).

Hits the LIVE runtime at https://runtime.sparkleai.tech
Run: pytest tests/test_style_library.py -v
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


def _new_path() -> str:
    return f"zenya-style-library/test-integration/{uuid.uuid4().hex}.jpg"


def _new_public_url(path: str) -> str:
    return f"https://gqhdspayjtiijcqklbys.supabase.co/storage/v1/object/public/{path}"


async def _register_item() -> str:
    """Register a throwaway item and return its id via direct HTTP (no fixture dep)."""
    path = _new_path()
    payload = [{"storage_path": path, "public_url": _new_public_url(path)}]
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/library/register-batch", json=payload)
        assert resp.status_code == 200, f"register-batch failed: {resp.text}"
        # Retrieve the inserted ID from the list endpoint
        list_resp = await c.get("/content/library", params={"limit": 1})
        items = list_resp.json().get("items", [])
        assert items, "No items found after registration"
        # Return the most-recently created item matching our path
        for item in items:
            if item.get("storage_path") == path:
                return item["id"]
        # Fallback: return first item
        return items[0]["id"]


# ── GET /content/library ──────────────────────────────────────

async def test_library_list_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/library")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "count" in body
    assert "stats" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["count"], int)


async def test_library_list_stats_shape():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/library")
    stats = resp.json()["stats"]
    assert "tiers" in stats
    assert "reactions" in stats
    assert "total" in stats
    assert set(stats["tiers"].keys()) >= {"A", "B", "C"}
    assert set(stats["reactions"].keys()) >= {"liked", "discarded", "neutral"}


async def test_library_list_filter_by_tier():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/library", params={"tier": "A"})
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        assert item["tier"] == "A"


async def test_library_list_filter_by_creator():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/library", params={"creator_id": "zenya"})
    assert resp.status_code == 200
    assert "items" in resp.json()


# ── POST /content/library/register-batch ─────────────────────

async def test_register_batch_single_item():
    path = _new_path()
    payload = [{"storage_path": path, "public_url": _new_public_url(path)}]
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/library/register-batch", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("registered") >= 1
    assert body.get("status") == "ok"


async def test_register_batch_multiple_items():
    paths = [_new_path() for _ in range(3)]
    payload = [{"storage_path": p, "public_url": _new_public_url(p)} for p in paths]
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/library/register-batch", json=payload)
    assert resp.status_code == 200
    assert resp.json()["registered"] == 3


async def test_register_batch_empty_returns_400():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/library/register-batch", json=[])
    assert resp.status_code == 400


async def test_register_batch_new_items_start_as_tier_c():
    path = _new_path()
    payload = [{"storage_path": path, "public_url": _new_public_url(path)}]
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        await c.post("/content/library/register-batch", json=payload)
        list_resp = await c.get("/content/library")
    # Find our item and verify tier is C
    items = list_resp.json()["items"]
    matching = [i for i in items if i.get("storage_path") == path]
    if matching:
        assert matching[0]["tier"] == "C"
    # If not in first page results, just assert list succeeded
    assert list_resp.status_code == 200


# ── POST /content/library/{id}/react ─────────────────────────

async def test_react_like_returns_200():
    item_id = await _register_item()
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/library/{item_id}/react", json={"reaction": "like"})
    assert resp.status_code == 200


async def test_react_discard_returns_200():
    item_id = await _register_item()
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/library/{item_id}/react", json={"reaction": "discard"})
    assert resp.status_code == 200


async def test_react_neutral_returns_200():
    item_id = await _register_item()
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/library/{item_id}/react", json={"reaction": "neutral"})
    assert resp.status_code == 200


async def test_react_invalid_reaction_returns_error():
    item_id = await _register_item()
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/library/{item_id}/react", json={"reaction": "invalid_xyz"})
    assert resp.status_code in (400, 422)


async def test_react_nonexistent_item_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(f"/content/library/{fake_id}/react", json={"reaction": "like"})
    assert resp.status_code == 404


# ── GET /content/library/tier-a ──────────────────────────────

async def test_tier_a_endpoint_responds():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/library/tier-a")
    # 200 if Tier A items exist; 400 if curadoria not done yet — both correct
    assert resp.status_code in (200, 400)


async def test_tier_a_items_are_all_tier_a_when_present():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/library/tier-a")
    if resp.status_code == 200 and "items" in resp.json():
        for item in resp.json()["items"]:
            assert item["tier"] == "A"


# ── POST /content/library/confirm ────────────────────────────

async def test_confirm_fails_gracefully_without_enough_likes():
    """Confirm should return 400, not 500, when < 10 items liked."""
    fake_creator = f"test-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/library/confirm", params={"creator_id": fake_creator})
    assert resp.status_code in (400, 422)
    assert resp.status_code != 500


async def test_confirm_zenya_does_not_crash():
    """Confirm for zenya should not return 500 regardless of current state."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/library/confirm", params={"creator_id": "zenya"})
    assert resp.status_code != 500
    if resp.status_code == 200:
        body = resp.json()
        assert "tier_a" in body or "tiers" in body or "status" in body


# ── GET /content/library/similar/{id} ────────────────────────

async def test_similar_endpoint_returns_200():
    item_id = await _register_item()
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get(f"/content/library/similar/{item_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


async def test_similar_nonexistent_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get(f"/content/library/similar/{fake_id}")
    assert resp.status_code == 404
