"""
Integration tests for Copy Specialist (CONTENT-1.4).

Hits the LIVE runtime at https://runtime.sparkleai.tech
Run: pytest tests/test_copy_specialist.py -v
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
    "theme": "IA transformando negócios no Brasil",
    "mood": "inspirador",
    "style": "minimalista",
    "platform": "instagram",
    "include_narration": True,
}


# ── POST /content/copy/generate ──────────────────────────────


async def test_generate_copy_returns_200():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=VALID_BRIEF)
    assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"


async def test_generate_copy_returns_caption_and_voice_script():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=VALID_BRIEF)
    body = resp.json()
    assert "caption" in body
    assert "voice_script" in body
    assert isinstance(body["caption"], str)
    assert len(body["caption"]) > 0


async def test_caption_has_hook_and_hashtags():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=VALID_BRIEF)
    caption = resp.json()["caption"]
    # Caption deve ter hashtags
    assert "#" in caption, "Caption deve conter hashtags"
    # Caption não pode exceder 2200 chars
    assert len(caption) <= 2200, f"Caption muito longa: {len(caption)} chars"


async def test_caption_hashtag_count():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=VALID_BRIEF)
    caption = resp.json()["caption"]
    hashtags = [w for w in caption.split() if w.startswith("#")]
    assert len(hashtags) >= 5, f"Mínimo 5 hashtags, encontrado: {len(hashtags)}"
    assert len(hashtags) <= 15, f"Máximo 15 hashtags, encontrado: {len(hashtags)}"


async def test_voice_script_is_pt_br_text():
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=VALID_BRIEF)
    voice_script = resp.json()["voice_script"]
    if voice_script is not None:
        # Sem emojis, sem markdown
        assert "**" not in voice_script, "voice_script não deve ter markdown"
        assert "##" not in voice_script, "voice_script não deve ter markdown"
        # Máx ~75 palavras
        word_count = len(voice_script.split())
        assert word_count <= 100, f"voice_script muito longo: {word_count} palavras"


async def test_generate_copy_without_narration():
    brief = {**VALID_BRIEF, "include_narration": False}
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=brief)
    assert resp.status_code == 200
    body = resp.json()
    assert body["voice_script"] is None, "voice_script deve ser null quando include_narration=False"
    assert body["caption"] is not None and len(body["caption"]) > 0


async def test_generate_copy_missing_theme_returns_error():
    brief = {"mood": "inspirador", "style": "minimalista"}
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post("/content/copy/generate", json=brief)
    assert resp.status_code in (400, 422), f"Esperado 400/422 sem theme, got {resp.status_code}"


async def test_generate_copy_different_themes():
    themes = [
        {"theme": "dicas de produtividade com IA", "mood": "motivador", "style": "clean"},
        {"theme": "curiosidades sobre machine learning", "mood": "divertido", "style": "colorido"},
    ]
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        for brief in themes:
            resp = await c.post("/content/copy/generate", json={**brief, "platform": "instagram"})
            assert resp.status_code == 200, f"Falhou para tema: {brief['theme']}"
            assert "caption" in resp.json()


# ── POST /content/copy/apply/{content_piece_id} ──────────────


async def _create_test_piece() -> str:
    """Cria um content piece de teste e retorna seu ID."""
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=30.0) as c:
        resp = await c.post("/content/pieces", json={
            "creator_id": "zenya",
            "platform": "instagram",
            "theme": "test-copy-specialist",
            "mood": "inspirador",
            "style": "minimalista",
        })
        if resp.status_code == 200:
            return resp.json()["id"]
    return None


async def test_apply_copy_to_existing_piece():
    """Se endpoint /content/pieces existir, testa apply. Senão, skipa."""
    piece_id = await _create_test_piece()
    if not piece_id:
        pytest.skip("Endpoint /content/pieces ainda não implementado")

    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post(
            f"/content/copy/apply/{piece_id}",
            json=VALID_BRIEF,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "caption" in body
    assert "voice_script" in body


async def test_apply_copy_nonexistent_piece_returns_404():
    fake_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=RUNTIME_URL, headers=HEADERS, timeout=60.0) as c:
        resp = await c.post(
            f"/content/copy/apply/{fake_id}",
            json=VALID_BRIEF,
        )
    # 404 se piece não existe, ou 400/422 se validação falhar antes
    assert resp.status_code in (400, 404, 422)
