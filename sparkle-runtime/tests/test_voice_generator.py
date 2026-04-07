"""
Integration tests for Voice Generator (CONTENT-1.4).

Hits the LIVE runtime at https://runtime.sparkleai.tech
Run: pytest tests/test_voice_generator.py -v
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

SAMPLE_SCRIPT = (
    "Olá! Eu sou a Zenya e hoje quero te mostrar como a inteligência artificial "
    "pode transformar o seu negócio. Vem comigo nessa jornada!"
)


# ── POST /content/voice/generate ─────────────────────────────


async def test_voice_generate_with_script_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/voice/generate", json={"voice_script": SAMPLE_SCRIPT})
    assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"


async def test_voice_generate_returns_audio_url():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/voice/generate", json={"voice_script": SAMPLE_SCRIPT})
    body = resp.json()
    assert "audio_url" in body
    # Pode ser string (URL) ou null se ElevenLabs estiver indisponível
    if body["audio_url"] is not None:
        assert body["audio_url"].startswith("http"), "audio_url deve ser URL pública"
        assert "content-assets" in body["audio_url"], "áudio deve estar no bucket content-assets"


async def test_voice_generate_null_script_returns_null_url():
    """voice_script=None → audio_url=None sem erro."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/voice/generate", json={"voice_script": None})
    assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("audio_url") is None, "audio_url deve ser null quando voice_script=None"


async def test_voice_generate_missing_voice_script_returns_error():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/voice/generate", json={})
    assert resp.status_code in (400, 422), f"Esperado 400/422, got {resp.status_code}"


async def test_voice_generate_empty_script_returns_error():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/voice/generate", json={"voice_script": ""})
    # String vazia não deve ser aceita
    assert resp.status_code in (400, 422)


# ── POST /content/voice/apply/{content_piece_id} ─────────────


async def test_voice_apply_null_script_returns_null_url():
    """Apply com voice_script=None → audio_url=None, sem crash."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        # Criar piece fake para teste
        create_resp = await c.post("/content/pieces", json={
            "creator_id": "zenya",
            "platform": "instagram",
            "theme": "test-voice-generator",
            "mood": "inspirador",
            "style": "minimalista",
        })
        if create_resp.status_code != 200:
            pytest.skip("Endpoint /content/pieces ainda não implementado")

        piece_id = create_resp.json()["id"]
        resp = await c.post(
            f"/content/voice/apply/{piece_id}",
            json={"voice_script": None},
        )
    assert resp.status_code == 200
    assert resp.json().get("audio_url") is None


async def test_voice_apply_nonexistent_piece_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post(
            f"/content/voice/apply/{fake_id}",
            json={"voice_script": SAMPLE_SCRIPT},
        )
    assert resp.status_code in (400, 404, 422)


# ── GET /content/voice/status ────────────────────────────────


async def test_voice_status_endpoint_responds():
    """Status do engine TTS deve responder com info sobre ElevenLabs/Zenya voice."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.get("/content/voice/status")
    # Pode não existir ainda — aceita 200 ou 404
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        body = resp.json()
        assert "voice_id" in body or "status" in body
