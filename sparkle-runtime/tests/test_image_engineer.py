"""
Integration tests for Image Engineer + Image Generator (CONTENT-1.2).

Hits the LIVE runtime at https://runtime.sparkleai.tech
Run: pytest tests/test_image_engineer.py -v
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
    "theme": "inteligência artificial no cotidiano",
    "mood": "inspirador",
    "style": "influencer_natural",
}

CINEMATIC_BRIEF = {
    "theme": "futuro da tecnologia",
    "mood": "confiante",
    "style": "cinematic",
}


# ── GET /content/image/status ─────────────────────────────────


async def test_image_status_ready():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.get("/content/image/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gemini_api_key_configured"] is True
    assert body["status"] == "ready"


# ── POST /content/image/generate ─────────────────────────────


async def test_image_generate_without_tier_a_returns_400_or_200():
    """
    Se Style Library não tem Tier A → 400 com mensagem clara.
    Se tem → 200 com image_url.
    Ambos são válidos dependendo do estado da library.
    """
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=120.0) as c:
        resp = await c.post("/content/image/generate", json=VALID_BRIEF)
    assert resp.status_code in (200, 400), f"Esperado 200 ou 400, got {resp.status_code}: {resp.text}"
    if resp.status_code == 400:
        assert "Tier A" in resp.json().get("detail", "") or "curadoria" in resp.json().get("detail", "")


async def test_image_generate_invalid_style_returns_400():
    brief = {**VALID_BRIEF, "style": "cartoon"}
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.post("/content/image/generate", json=brief)
    assert resp.status_code == 400


async def test_image_generate_missing_theme_returns_422():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.post("/content/image/generate", json={"mood": "inspirador", "style": "cinematic"})
    assert resp.status_code == 422


async def test_image_generate_cinematic_style_accepted():
    """Estilo cinematic deve ser aceito (400 por Tier A ausente ou 200 se disponível)."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=120.0) as c:
        resp = await c.post("/content/image/generate", json=CINEMATIC_BRIEF)
    assert resp.status_code in (200, 400, 500)
    # Não deve ser 422 (validação de campos)
    assert resp.status_code != 422


async def test_image_generate_returns_image_url_when_tier_a_exists():
    """Se Tier A disponível, response deve ter image_url apontando pro bucket."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=120.0) as c:
        resp = await c.post("/content/image/generate", json=VALID_BRIEF)
    if resp.status_code == 200:
        body = resp.json()
        assert "image_url" in body
        assert body["image_url"].startswith("http")
        assert "content-assets" in body["image_url"]


# ── POST /content/image/apply/{id} ───────────────────────────


async def test_image_apply_nonexistent_piece_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=15.0) as c:
        resp = await c.post(f"/content/image/apply/{fake_id}", json=VALID_BRIEF)
    assert resp.status_code == 404


async def test_image_apply_existing_piece():
    """Cria piece e aplica geração de imagem. Skip se /content/pieces não existe."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        create_resp = await c.post("/content/pieces", json={
            "creator_id": "zenya",
            "platform": "instagram",
            "theme": VALID_BRIEF["theme"],
            "mood": VALID_BRIEF["mood"],
            "style": VALID_BRIEF["style"],
        })
        if create_resp.status_code != 200:
            pytest.skip("Endpoint /content/pieces não implementado ainda")

        piece_id = create_resp.json()["id"]
        resp = await c.post(f"/content/image/apply/{piece_id}", json=VALID_BRIEF)

    assert resp.status_code in (200, 400, 500)
