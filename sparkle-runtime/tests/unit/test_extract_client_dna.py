"""
Unit tests for extract_client_dna handler (B2-04).

Tests DNA extraction, JSON parsing, confidence scoring, category filtering,
and the main handler flow with mocked LLM and DB.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Constants tests ─────────────────────────────────────────────────────────

def test_dna_categories_count():
    from runtime.tasks.handlers.extract_client_dna import DNA_CATEGORIES
    assert len(DNA_CATEGORIES) == 8


def test_dna_categories_required():
    from runtime.tasks.handlers.extract_client_dna import DNA_CATEGORIES

    expected = {"tom", "persona", "regras", "diferenciais", "publico_alvo", "produtos", "objecoes", "faq"}
    assert set(DNA_CATEGORIES) == expected


def test_category_descriptions_complete():
    from runtime.tasks.handlers.extract_client_dna import _CATEGORY_DESCRIPTIONS, DNA_CATEGORIES

    for cat in DNA_CATEGORIES:
        assert cat in _CATEGORY_DESCRIPTIONS, f"Missing description for '{cat}'"
        assert len(_CATEGORY_DESCRIPTIONS[cat]) > 10


# ── _parse_json_response tests ──────────────────────────────────────────────

def test_parse_json_clean():
    from runtime.tasks.handlers.extract_client_dna import _parse_json_response

    raw = '{"items": [{"category": "tom"}], "summary": "test"}'
    result = _parse_json_response(raw)
    assert result["items"][0]["category"] == "tom"


def test_parse_json_with_markdown_fences():
    from runtime.tasks.handlers.extract_client_dna import _parse_json_response

    raw = '```json\n{"items": [], "summary": "ok"}\n```'
    result = _parse_json_response(raw)
    assert result is not None
    assert result["summary"] == "ok"


def test_parse_json_invalid():
    from runtime.tasks.handlers.extract_client_dna import _parse_json_response

    result = _parse_json_response("This is not JSON")
    assert result is None


def test_parse_json_empty_string():
    from runtime.tasks.handlers.extract_client_dna import _parse_json_response

    result = _parse_json_response("")
    assert result is None


# ── _count_categories tests ─────────────────────────────────────────────────

def test_count_categories():
    from runtime.tasks.handlers.extract_client_dna import _count_categories

    items = [
        {"category": "tom"},
        {"category": "tom"},
        {"category": "persona"},
        {"category": "faq"},
    ]
    counts = _count_categories(items)
    assert counts == {"tom": 2, "persona": 1, "faq": 1}


def test_count_categories_empty():
    from runtime.tasks.handlers.extract_client_dna import _count_categories

    assert _count_categories([]) == {}


def test_count_categories_unknown():
    from runtime.tasks.handlers.extract_client_dna import _count_categories

    items = [{"category": "unknown_cat"}]
    counts = _count_categories(items)
    assert counts == {"unknown_cat": 1}


# ── handle_extract_client_dna tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_handler_missing_client_id():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    result = await handle_extract_client_dna({"payload": {}})
    assert "error" in result
    assert "client_id" in result["error"].lower()


@pytest.mark.asyncio
async def test_handler_no_chunks():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    with patch("runtime.tasks.handlers.extract_client_dna._get_client_chunks", new_callable=AsyncMock, return_value=[]):
        result = await handle_extract_client_dna({"payload": {"client_id": "test-001"}})
    assert "error" in result
    assert "chunk" in result["error"].lower()


@pytest.mark.asyncio
async def test_handler_llm_returns_no_items():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    chunks = [{"id": "c1", "raw_content": "test", "source_type": "web_url", "source_title": "Test"}]
    llm_response = json.dumps({"items": [], "summary": "nothing found"})

    with patch("runtime.tasks.handlers.extract_client_dna._get_client_chunks", new_callable=AsyncMock, return_value=chunks), \
         patch("runtime.tasks.handlers.extract_client_dna.call_claude", new_callable=AsyncMock, return_value=llm_response):
        result = await handle_extract_client_dna({"payload": {"client_id": "test-001"}})
    assert "error" in result


@pytest.mark.asyncio
async def test_handler_success_flow():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    chunks = [
        {"id": f"chunk-{i}", "raw_content": f"Content {i}", "source_type": "web_url", "source_title": f"Page {i}"}
        for i in range(5)
    ]
    llm_items = [
        {"category": "tom", "key": "informal", "title": "Tom informal", "content": "Usa linguagem informal", "confidence": 0.85},
        {"category": "persona", "key": "jovem", "title": "Marca jovem", "content": "Marca com pegada jovem", "confidence": 0.9},
        {"category": "faq", "key": "preco", "title": "Preco", "content": "A partir de R$50", "confidence": 0.7},
    ]
    llm_response = json.dumps({"items": llm_items, "summary": "Negocio informal e jovem"})

    with patch("runtime.tasks.handlers.extract_client_dna._get_client_chunks", new_callable=AsyncMock, return_value=chunks), \
         patch("runtime.tasks.handlers.extract_client_dna.call_claude", new_callable=AsyncMock, return_value=llm_response), \
         patch("runtime.tasks.handlers.extract_client_dna._persist_dna_items", new_callable=AsyncMock, return_value=3), \
         patch("runtime.tasks.handlers.extract_client_dna._get_next_version", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._update_zenya_client", new_callable=AsyncMock), \
         patch("runtime.tasks.handlers.extract_client_dna._generate_soul_prompt_from_items", new_callable=AsyncMock, return_value="Soul prompt text"), \
         patch("runtime.tasks.handlers.extract_client_dna._mark_chunks_processed", new_callable=AsyncMock):
        result = await handle_extract_client_dna({"id": "task-001", "payload": {"client_id": "test-001"}})

    assert result["items_extracted"] == 3
    assert result["rows_inserted"] == 3
    assert result["categories"] == {"tom": 1, "persona": 1, "faq": 1}
    assert result["soul_prompt_generated"] is True
    assert result["client_id"] == "test-001"


@pytest.mark.asyncio
async def test_handler_category_filter():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    chunks = [{"id": "c1", "raw_content": "test", "source_type": "web_url", "source_title": "T"}]
    llm_items = [
        {"category": "tom", "key": "k1", "title": "T1", "content": "C1", "confidence": 0.8},
        {"category": "persona", "key": "k2", "title": "T2", "content": "C2", "confidence": 0.8},
        {"category": "faq", "key": "k3", "title": "T3", "content": "C3", "confidence": 0.8},
    ]
    llm_response = json.dumps({"items": llm_items, "summary": "ok"})

    with patch("runtime.tasks.handlers.extract_client_dna._get_client_chunks", new_callable=AsyncMock, return_value=chunks), \
         patch("runtime.tasks.handlers.extract_client_dna.call_claude", new_callable=AsyncMock, return_value=llm_response), \
         patch("runtime.tasks.handlers.extract_client_dna._persist_dna_items", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._get_next_version", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._update_zenya_client", new_callable=AsyncMock), \
         patch("runtime.tasks.handlers.extract_client_dna._generate_soul_prompt_from_items", new_callable=AsyncMock, return_value=None), \
         patch("runtime.tasks.handlers.extract_client_dna._mark_chunks_processed", new_callable=AsyncMock):
        result = await handle_extract_client_dna({
            "id": "task-001",
            "payload": {"client_id": "test-001", "categories": ["tom"]}
        })

    # Only "tom" items should be passed to persist
    assert result["items_extracted"] == 1


@pytest.mark.asyncio
async def test_handler_confidence_high_with_many_chunks():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    chunks = [{"id": f"c{i}", "raw_content": f"Content {i}", "source_type": "web_url", "source_title": f"P{i}"} for i in range(15)]
    llm_items = [{"category": "tom", "key": "k1", "title": "T", "content": "C", "confidence": 0.8}]
    llm_response = json.dumps({"items": llm_items, "summary": "ok"})

    with patch("runtime.tasks.handlers.extract_client_dna._get_client_chunks", new_callable=AsyncMock, return_value=chunks), \
         patch("runtime.tasks.handlers.extract_client_dna.call_claude", new_callable=AsyncMock, return_value=llm_response), \
         patch("runtime.tasks.handlers.extract_client_dna._persist_dna_items", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._get_next_version", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._update_zenya_client", new_callable=AsyncMock), \
         patch("runtime.tasks.handlers.extract_client_dna._generate_soul_prompt_from_items", new_callable=AsyncMock, return_value=None), \
         patch("runtime.tasks.handlers.extract_client_dna._mark_chunks_processed", new_callable=AsyncMock):
        result = await handle_extract_client_dna({"id": "t1", "payload": {"client_id": "test-001", "regenerate_prompt": False}})

    assert result["confidence"] == "high"


@pytest.mark.asyncio
async def test_handler_confidence_medium_with_few_chunks():
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    chunks = [{"id": f"c{i}", "raw_content": f"Content {i}", "source_type": "web_url", "source_title": f"P{i}"} for i in range(5)]
    llm_items = [{"category": "tom", "key": "k1", "title": "T", "content": "C", "confidence": 0.8}]
    llm_response = json.dumps({"items": llm_items, "summary": "ok"})

    with patch("runtime.tasks.handlers.extract_client_dna._get_client_chunks", new_callable=AsyncMock, return_value=chunks), \
         patch("runtime.tasks.handlers.extract_client_dna.call_claude", new_callable=AsyncMock, return_value=llm_response), \
         patch("runtime.tasks.handlers.extract_client_dna._persist_dna_items", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._get_next_version", new_callable=AsyncMock, return_value=1), \
         patch("runtime.tasks.handlers.extract_client_dna._update_zenya_client", new_callable=AsyncMock), \
         patch("runtime.tasks.handlers.extract_client_dna._generate_soul_prompt_from_items", new_callable=AsyncMock, return_value=None), \
         patch("runtime.tasks.handlers.extract_client_dna._mark_chunks_processed", new_callable=AsyncMock):
        result = await handle_extract_client_dna({"id": "t1", "payload": {"client_id": "test-001", "regenerate_prompt": False}})

    assert result["confidence"] == "medium"
