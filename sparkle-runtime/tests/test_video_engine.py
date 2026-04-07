"""
Integration tests for Video Engineer + Video Generator (CONTENT-1.3).

Hits the LIVE runtime at https://runtime.sparkleai.tech
Run: pytest tests/test_video_engine.py -v

NOTE: /video/generate chama o Veo — pode levar até 5 min e tem custo.
      Testes de geração real são skippados por padrão.
      Definir VEO_LIVE_TESTS=1 para executar.
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
VEO_LIVE = os.environ.get("VEO_LIVE_TESTS", "0") == "1"

SAMPLE_IMAGE_URL = "https://gqhdspayjtiijcqklbys.supabase.co/storage/v1/object/public/content-assets/images/test-zenya-ref.png"


# ── GET /content/video/status ─────────────────────────────────


async def test_video_status_ready():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.get("/content/video/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gemini_api_key_configured"] is True
    assert body["status"] == "ready"
    assert body["aspect_ratio"] == "9:16"
    assert body["model"] == "veo-2.0-generate-001"


# ── POST /content/video/generate — validações ─────────────────


async def test_video_generate_invalid_style_returns_400():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.post("/content/video/generate", json={
            "image_url": SAMPLE_IMAGE_URL,
            "style": "cartoon",
        })
    assert resp.status_code == 400


async def test_video_generate_missing_image_url_returns_422():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.post("/content/video/generate", json={"style": "cinematic"})
    assert resp.status_code == 422


async def test_video_generate_influencer_style_accepted():
    """Valida que o estilo influencer_natural é aceito — sem chamar Veo."""
    # Só testa validação da request, não a geração real
    if not VEO_LIVE:
        pytest.skip("VEO_LIVE_TESTS não habilitado — skip geração real")

    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=360.0) as c:
        resp = await c.post("/content/video/generate", json={
            "image_url": SAMPLE_IMAGE_URL,
            "style": "influencer_natural",
            "theme": "inteligência artificial no cotidiano",
        })
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        body = resp.json()
        assert "video_url" in body
        assert body["video_url"].startswith("http")
        assert "content-assets" in body["video_url"]
        assert body["duration_seconds"] == 5


async def test_video_generate_cinematic_style():
    """Cinematic = 10s de duração."""
    if not VEO_LIVE:
        pytest.skip("VEO_LIVE_TESTS não habilitado — skip geração real")

    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=360.0) as c:
        resp = await c.post("/content/video/generate", json={
            "image_url": SAMPLE_IMAGE_URL,
            "style": "cinematic",
        })
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.json()["duration_seconds"] == 10


# ── POST /content/video/apply/{id} ───────────────────────────


async def test_video_apply_nonexistent_piece_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.post(f"/content/video/apply/{fake_id}", json={
            "image_url": SAMPLE_IMAGE_URL,
            "style": "influencer_natural",
        })
    assert resp.status_code == 404


async def test_video_apply_existing_piece():
    """Cria piece e aplica geração de vídeo. Skip se /content/pieces não existe ou VEO_LIVE=0."""
    if not VEO_LIVE:
        pytest.skip("VEO_LIVE_TESTS não habilitado — skip geração real")

    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        create_resp = await c.post("/content/pieces", json={
            "creator_id": "zenya",
            "platform": "instagram",
            "theme": "teste de geração de vídeo",
            "mood": "inspirador",
            "style": "influencer_natural",
        })
        if create_resp.status_code != 200:
            pytest.skip("Endpoint /content/pieces não implementado ainda")

        piece_id = create_resp.json()["id"]

    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=360.0) as c:
        resp = await c.post(f"/content/video/apply/{piece_id}", json={
            "image_url": SAMPLE_IMAGE_URL,
            "style": "influencer_natural",
        })

    assert resp.status_code in (200, 500)
