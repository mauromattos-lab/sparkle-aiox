"""
Unit tests for W1-BRAIN-1 — Flywheel: Content Approval → Brain Ingest.

Tests:
  - namespace.py: _SOURCE_TYPE_MAP has 'published_reel' → 'sparkle-lore'
  - approval.py: approve_piece() fires _ingest_approved_to_brain() non-blocking
  - approval.py: _ingest_approved_to_brain() calls ingest-pipeline with correct payload
  - publisher.py: _ingest_published_to_brain() uses ingest-pipeline (not direct insert)
  - publisher.py: brain_owner=content, namespace=sparkle-lore via _SOURCE_TYPE_MAP

Run: pytest tests/unit/test_content_brain_flywheel.py -v
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════

FAKE_PIECE = {
    "id": "piece-flywheel-test-001",
    "status": "pending_approval",
    "theme": "IA para PMEs — O Futuro Chegou",
    "caption": "Zenya te mostra como automatizar tudo #ia #pme",
    "voice_script": "Olá! Sou a Zenya e hoje vou te mostrar como a IA pode...",
    "character": "zenya",
    "content_type": "reel",
    "pipeline_log": [],
    "brain_chunk_id": None,
    "published_url": None,
    "published_at": None,
    "scheduled_at": None,
    "approved_at": None,
    "creator_id": None,
}


def _make_piece(**overrides) -> dict:
    return {**FAKE_PIECE, **overrides}


# ════════════════════════════════════════════════════════════════════════
# T1 — namespace.py: _SOURCE_TYPE_MAP mapping
# ════════════════════════════════════════════════════════════════════════

class TestNamespaceMapping:
    """AC-6: source_type 'published_reel' maps to 'sparkle-lore' in namespace.py."""

    def test_published_reel_maps_to_sparkle_lore(self):
        """_SOURCE_TYPE_MAP['published_reel'] == 'sparkle-lore'"""
        from runtime.brain.namespace import _SOURCE_TYPE_MAP
        assert _SOURCE_TYPE_MAP.get("published_reel") == "sparkle-lore", (
            "published_reel must map to sparkle-lore in _SOURCE_TYPE_MAP"
        )

    def test_approved_reel_maps_to_sparkle_lore(self):
        """_SOURCE_TYPE_MAP['approved_reel'] == 'sparkle-lore'"""
        from runtime.brain.namespace import _SOURCE_TYPE_MAP
        assert _SOURCE_TYPE_MAP.get("approved_reel") == "sparkle-lore", (
            "approved_reel must map to sparkle-lore in _SOURCE_TYPE_MAP"
        )

    def test_resolve_namespace_published_reel(self):
        """resolve_namespace with source_type metadata returns 'sparkle-lore'."""
        from runtime.brain.namespace import resolve_namespace
        ns = resolve_namespace(metadata={"source_type": "published_reel"})
        assert ns == "sparkle-lore"

    def test_resolve_namespace_explicit_override(self):
        """Explicit namespace in metadata takes priority (priority 1)."""
        from runtime.brain.namespace import resolve_namespace
        ns = resolve_namespace(metadata={"namespace": "sparkle-lore", "source_type": "youtube"})
        assert ns == "sparkle-lore"

    def test_sparkle_lore_is_valid_namespace(self):
        """'sparkle-lore' must be in SEMANTIC_NAMESPACES."""
        from runtime.brain.namespace import SEMANTIC_NAMESPACES, is_valid_namespace
        assert "sparkle-lore" in SEMANTIC_NAMESPACES
        assert is_valid_namespace("sparkle-lore")


# ════════════════════════════════════════════════════════════════════════
# T2 — publisher.py: _ingest_published_to_brain uses ingest-pipeline
# ════════════════════════════════════════════════════════════════════════

class TestPublisherBrainIngest:
    """AC-4: publisher._ingest_published_to_brain uses POST /brain/ingest-pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_published_calls_pipeline_not_direct_insert(self):
        """_ingest_published_to_brain must POST to ingest-pipeline, not insert to brain_chunks."""
        import httpx
        from unittest.mock import patch, AsyncMock

        # Mock httpx.AsyncClient to capture the POST
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "chunk_ids": ["chunk-test-abc-123"],
        }

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.content.publisher.supabase") as mock_sb, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = "test-key"
            mock_settings.instagram_access_token = "ig-token"
            mock_settings.instagram_user_id = "ig-user"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from runtime.content import publisher
            piece = _make_piece(published_url="https://www.instagram.com/p/test123/")
            result = await publisher._ingest_published_to_brain(piece)

        # Must have called POST (ingest-pipeline), not supabase.table("brain_chunks").insert
        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert "/brain/ingest-pipeline" in call_url, (
            f"Expected call to /brain/ingest-pipeline, got: {call_url}"
        )

        # brain_chunks.insert must NOT have been called
        if hasattr(mock_sb, "table"):
            for call_args in mock_sb.table.call_args_list:
                table_name = call_args[0][0] if call_args[0] else ""
                assert table_name != "brain_chunks", (
                    "Direct insert to brain_chunks detected — must use ingest-pipeline"
                )

    @pytest.mark.asyncio
    async def test_ingest_published_payload_has_correct_fields(self):
        """Payload to ingest-pipeline has persona=especialista, source_type=published_reel."""
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "chunk_ids": ["chunk-xyz"]}

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.content.publisher.supabase"), \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = None

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from runtime.content import publisher
            piece = _make_piece(
                theme="Automacao para PMEs",
                caption="Caption de teste",
                voice_script="Script de teste",
                published_url="https://www.instagram.com/p/abc/",
            )
            await publisher._ingest_published_to_brain(piece)

        payload = mock_client.post.call_args.kwargs.get("json") or {}
        assert payload.get("source_type") == "published_reel"
        assert payload.get("persona") == "especialista"
        assert payload.get("client_id") is None

        # raw_content must include key piece fields
        raw = payload.get("raw_content", "")
        assert "Automacao para PMEs" in raw
        assert "Caption de teste" in raw

    @pytest.mark.asyncio
    async def test_ingest_published_returns_none_on_pipeline_error(self):
        """If ingest-pipeline returns error, function returns None (non-blocking)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.content.publisher.supabase"), \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = None

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from runtime.content import publisher
            result = await publisher._ingest_published_to_brain(_make_piece())

        assert result is None, "Must return None on pipeline error (non-blocking)"


# ════════════════════════════════════════════════════════════════════════
# T3/T4 — approval.py: _ingest_approved_to_brain hook
# ════════════════════════════════════════════════════════════════════════

class TestApprovalBrainHook:
    """AC-1: approve_piece() fires brain ingest non-blocking via ingest-pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_approved_calls_pipeline(self):
        """_ingest_approved_to_brain posts to /brain/ingest-pipeline with correct payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "chunk_ids": ["chunk-approved-001"]}

        with patch("runtime.content.approval.settings") as mock_settings, \
             patch("runtime.content.approval.supabase"), \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = "test-key"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from runtime.content import approval
            piece = _make_piece(
                theme="Tema de teste aprovacao",
                caption="Caption aprovado",
                voice_script="Script aprovado",
            )
            await approval._ingest_approved_to_brain(piece)

        # Must have called ingest-pipeline
        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert "/brain/ingest-pipeline" in call_url

        payload = mock_client.post.call_args.kwargs.get("json") or {}
        assert payload.get("source_type") == "published_reel"
        assert payload.get("persona") == "especialista"
        assert payload.get("client_id") is None

    @pytest.mark.asyncio
    async def test_ingest_approved_stores_brain_chunk_id(self):
        """After successful ingest, brain_chunk_id is persisted to content_pieces."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "chunk_ids": ["chunk-stored-abc"]}

        captured_updates = {}

        def fake_update(fields):
            captured_updates.update(fields)
            mock_chain = MagicMock()
            mock_chain.eq.return_value = mock_chain
            mock_chain.execute.return_value = MagicMock(data=[])
            return mock_chain

        with patch("runtime.content.approval.settings") as mock_settings, \
             patch("runtime.content.approval.supabase") as mock_sb, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = None

            # Mock supabase table chain
            mock_table = MagicMock()
            mock_table.update = fake_update
            mock_sb.table.return_value = mock_table

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from runtime.content import approval
            await approval._ingest_approved_to_brain(_make_piece())

        assert "brain_chunk_id" in captured_updates, "brain_chunk_id must be persisted after ingest"
        assert captured_updates["brain_chunk_id"] == "chunk-stored-abc"

    @pytest.mark.asyncio
    async def test_ingest_approved_does_not_raise_on_error(self):
        """Brain ingest failure must not raise — approval flow must remain unaffected."""
        with patch("runtime.content.approval.settings") as mock_settings, \
             patch("runtime.content.approval.supabase"), \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = None

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=ConnectionError("network down"))
            mock_client_cls.return_value = mock_client

            from runtime.content import approval
            # Must not raise
            await approval._ingest_approved_to_brain(_make_piece())

    @pytest.mark.asyncio
    async def test_ingest_approved_includes_metadata_header(self):
        """Payload raw_content includes metadata header with piece_id and character."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "chunk_ids": []}

        with patch("runtime.content.approval.settings") as mock_settings, \
             patch("runtime.content.approval.supabase"), \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_settings.runtime_api_key = None

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from runtime.content import approval
            piece = _make_piece(theme="Test tema", caption="Test caption", voice_script="Test script")
            await approval._ingest_approved_to_brain(piece)

        payload = mock_client.post.call_args.kwargs.get("json") or {}
        raw = payload.get("raw_content", "")
        assert "content_piece_id=" in raw, "metadata header must include content_piece_id"
        assert "character=" in raw, "metadata header must include character"
        assert "Test tema" in raw, "raw_content must include theme"


# ════════════════════════════════════════════════════════════════════════
# T6 — publisher.py: _update_chunk_instagram_url
# ════════════════════════════════════════════════════════════════════════

class TestChunkInstagramUrlUpdate:
    """AC-4 T6: After Instagram publish, chunk metadata is updated with instagram_url."""

    @pytest.mark.asyncio
    async def test_update_chunk_instagram_url(self):
        """_update_chunk_instagram_url updates chunk_metadata with instagram_url."""
        existing_meta = {"content_piece_id": "piece-001", "character": "zenya"}

        mock_select_result = MagicMock()
        mock_select_result.data = [{"chunk_metadata": existing_meta}]

        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "chunk-001"}]

        updated_meta_captured = {}

        def fake_update(fields):
            updated_meta_captured.update(fields)
            mock_chain = MagicMock()
            mock_chain.eq.return_value = mock_chain
            mock_chain.execute.return_value = mock_update_result
            return mock_chain

        with patch("runtime.content.publisher.supabase") as mock_sb:
            # Mock select chain
            select_chain = MagicMock()
            select_chain.select.return_value = select_chain
            select_chain.eq.return_value = select_chain
            select_chain.limit.return_value = select_chain
            select_chain.execute.return_value = mock_select_result

            update_chain = MagicMock()
            update_chain.update = fake_update

            def table_router(name):
                if name == "brain_chunks":
                    # First call: select, second: update
                    if not hasattr(table_router, "_call_count"):
                        table_router._call_count = 0
                    table_router._call_count += 1
                    if table_router._call_count == 1:
                        return select_chain
                    return update_chain
                return MagicMock()

            mock_sb.table.side_effect = table_router

            from runtime.content import publisher
            await publisher._update_chunk_instagram_url(
                "chunk-001",
                "https://www.instagram.com/p/TESTURL/",
                "piece-001",
            )

        assert "chunk_metadata" in updated_meta_captured
        assert updated_meta_captured["chunk_metadata"]["instagram_url"] == "https://www.instagram.com/p/TESTURL/"
        assert "content_piece_id" in updated_meta_captured["chunk_metadata"]
