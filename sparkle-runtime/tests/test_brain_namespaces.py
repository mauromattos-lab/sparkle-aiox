"""
C2-B1: Tests for Brain Namespaces + Auto-Ingest Friday.

Covers:
  - Namespace registration in isolation.py
  - Seed idempotency (chunk_markdown + hash dedup)
  - Auto-ingest trigger logic
  - Noise filter
  - Metadata persistence in brain_ingest handler
  - Named namespace routing in get_brain_owner_for_ingest
"""
from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.brain.isolation import (
    NAMED_NAMESPACES,
    get_brain_owner_for_ingest,
    is_valid_namespace,
    validate_brain_access,
)
from runtime.brain.seed import chunk_markdown, _hash, NAMESPACE_SOURCES
from runtime.friday.dispatcher import (
    _should_auto_ingest,
    _fire_auto_ingest,
)


# ── 1. Namespace registration ─────────────────────────────────────────────


class TestNamespaceRegistration:
    def test_named_namespaces_contains_mauro_personal(self):
        assert "mauro-personal" in NAMED_NAMESPACES

    def test_named_namespaces_contains_sparkle_lore(self):
        assert "sparkle-lore" in NAMED_NAMESPACES

    def test_named_namespaces_contains_sparkle_ops(self):
        assert "sparkle-ops" in NAMED_NAMESPACES

    def test_is_valid_namespace_true(self):
        assert is_valid_namespace("mauro-personal") is True
        assert is_valid_namespace("sparkle-lore") is True
        assert is_valid_namespace("sparkle-ops") is True

    def test_is_valid_namespace_false_for_unknown(self):
        assert is_valid_namespace("random-namespace") is False
        assert is_valid_namespace("friday") is False

    def test_ingest_with_target_namespace_overrides(self):
        """get_brain_owner_for_ingest with target_namespace returns the namespace."""
        result = get_brain_owner_for_ingest(
            "friday", target_namespace="mauro-personal",
        )
        assert result == "mauro-personal"

    def test_ingest_with_invalid_target_namespace_falls_back(self):
        """Invalid target_namespace is ignored — falls back to agent slug logic."""
        result = get_brain_owner_for_ingest(
            "friday", target_namespace="nonexistent",
        )
        assert result == "friday"  # normal friday behavior

    def test_system_access_to_named_namespaces(self):
        """System/orion (unrestricted) can access named namespaces."""
        assert validate_brain_access("system", "mauro-personal") is True
        assert validate_brain_access("orion", "sparkle-lore") is True

    def test_friday_cannot_access_named_namespace_by_default(self):
        """Friday's default filter is 'friday' — cannot read mauro-personal."""
        assert validate_brain_access("friday", "mauro-personal") is False


# ── 2. Seed chunking + idempotency ────────────────────────────────────────


class TestSeedChunking:
    def test_chunk_markdown_splits_by_heading(self):
        text = "# Heading 1\n\nSome body text that is long enough to be a valid chunk content section.\n\n## Heading 2\n\nAnother section with enough content to pass the minimum character threshold for chunking."
        chunks = chunk_markdown(text, "test-file")
        assert len(chunks) >= 2

    def test_chunk_markdown_no_headings(self):
        text = "This is a plain text file with no headings but enough content to be a valid chunk. " * 3
        chunks = chunk_markdown(text, "test-file")
        assert len(chunks) == 1
        assert chunks[0]["section"] == "test-file"

    def test_chunk_markdown_skips_short_sections(self):
        text = "# H1\n\nShort.\n\n# H2\n\nAlso very short text."
        chunks = chunk_markdown(text, "test-file")
        # Both sections are under _MIN_CHUNK_CHARS (80), so should be empty
        assert len(chunks) == 0

    def test_chunk_content_hash_deterministic(self):
        content = "The same text always produces the same hash."
        h1 = _hash(content)
        h2 = _hash(content)
        assert h1 == h2
        assert h1 == hashlib.sha256(content.encode("utf-8")).hexdigest()

    def test_chunk_content_hash_differs_for_different_content(self):
        assert _hash("text one") != _hash("text two")

    def test_namespace_sources_defined_for_all_namespaces(self):
        """Every named namespace has at least one source file defined."""
        for ns in NAMED_NAMESPACES:
            assert ns in NAMESPACE_SOURCES, f"Missing sources for namespace: {ns}"
            assert len(NAMESPACE_SOURCES[ns]) > 0


# ── 3. Auto-ingest noise filter ───────────────────────────────────────────


class TestAutoIngestNoiseFilter:
    def test_echo_intent_blocked(self):
        assert _should_auto_ingest("echo test message", "echo") is False

    def test_short_chat_blocked(self):
        assert _should_auto_ingest("oi tudo bem", "chat") is False

    def test_long_chat_allowed(self):
        text = "precisamos repensar a estrategia de pricing para o proximo trimestre considerando os novos clientes"
        assert _should_auto_ingest(text, "chat") is True

    def test_very_short_any_intent_blocked(self):
        assert _should_auto_ingest("ok sim", "status_report") is False

    def test_substantial_status_report_allowed(self):
        text = "quero um relatorio completo de todos os agentes ativos e seus status atuais no sistema"
        assert _should_auto_ingest(text, "status_report") is True

    def test_brain_query_allowed(self):
        text = "brain o que voce sabe sobre a visao de longo prazo da sparkle e os planos para 2027"
        assert _should_auto_ingest(text, "brain_query") is True

    def test_create_note_allowed(self):
        text = "anota isso: decidimos que o pricing vai ser R$500 para o plano basico a partir de maio"
        assert _should_auto_ingest(text, "create_note") is True


# ── 4. Auto-ingest fire-and-forget ─────────────────────────────────────────


class TestAutoIngestFireAndForget:
    @pytest.mark.asyncio
    async def test_fire_auto_ingest_creates_task(self):
        """_fire_auto_ingest inserts a runtime_task with correct payload."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "auto-ingest-task-001"}]

        mock_query = MagicMock()
        mock_query.insert.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_query

        with patch("runtime.friday.dispatcher.supabase", mock_sb):
            with patch("runtime.tasks.worker.execute_task", new_callable=AsyncMock):
                await _fire_auto_ingest(
                    "decisao importante sobre pricing",
                    "create_note",
                )

        # Verify the insert was called
        mock_sb.table.assert_called_with("runtime_tasks")
        insert_call = mock_query.insert.call_args[0][0]
        assert insert_call["task_type"] == "brain_ingest"
        assert insert_call["payload"]["target_namespace"] == "mauro-personal"
        assert insert_call["payload"]["metadata"]["source"] == "friday-audio"
        assert insert_call["payload"]["metadata"]["intent"] == "create_note"
        assert "timestamp" in insert_call["payload"]["metadata"]

    @pytest.mark.asyncio
    async def test_fire_auto_ingest_does_not_raise_on_error(self):
        """_fire_auto_ingest silently logs errors — never raises."""
        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB connection failed")

        with patch("runtime.friday.dispatcher.supabase", mock_sb):
            # Should NOT raise
            await _fire_auto_ingest("some text", "chat")


# ── 5. Metadata persistence in brain_ingest handler ───────────────────────


class TestMetadataPersistence:
    @pytest.mark.asyncio
    async def test_extra_metadata_merged_into_chunk_metadata(self):
        """When payload has 'metadata' dict, it merges into chunk_metadata."""
        from runtime.tasks.handlers.brain_ingest import handle_brain_ingest

        mock_response = MagicMock()
        mock_response.data = [{"id": "chunk-meta-001"}]

        inserted_row = {}

        def capture_insert(row):
            inserted_row.update(row)
            mock_q = MagicMock()
            mock_q.execute.return_value = mock_response
            return mock_q

        mock_entities_resp = MagicMock()
        mock_entities_resp.data = []
        mock_entities_q = MagicMock()
        mock_entities_q.select.return_value = mock_entities_q
        mock_entities_q.eq.return_value = mock_entities_q
        mock_entities_q.execute.return_value = mock_entities_resp

        mock_sb = MagicMock()

        def table_router(name):
            if name == "brain_entities":
                return mock_entities_q
            mock_q = MagicMock()
            mock_q.insert.side_effect = capture_insert
            return mock_q

        mock_sb.table.side_effect = table_router

        task = {
            "id": "task-meta-001",
            "client_id": "sparkle-internal",
            "payload": {
                "content": "Important decision about system architecture",
                "source_agent": "mauro",
                "ingest_type": "mauro_audio",
                "target_namespace": "mauro-personal",
                "metadata": {
                    "source": "friday-audio",
                    "timestamp": "2026-04-05T12:00:00Z",
                    "intent": "create_note",
                },
            },
        }

        with patch("runtime.tasks.handlers.brain_ingest.supabase", mock_sb):
            with patch(
                "runtime.tasks.handlers.brain_ingest.get_embedding",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await handle_brain_ingest(task)

        assert "Anotado no Brain" in result["message"]
        # Verify metadata was merged
        chunk_meta = inserted_row.get("chunk_metadata", {})
        assert chunk_meta.get("source") == "friday-audio"
        assert chunk_meta.get("intent") == "create_note"
        assert chunk_meta.get("timestamp") == "2026-04-05T12:00:00Z"
        # Original fields still present
        assert chunk_meta.get("source_agent") == "mauro"
        assert chunk_meta.get("ingest_type") == "mauro_audio"

    @pytest.mark.asyncio
    async def test_target_namespace_routes_to_named_namespace(self):
        """When payload has target_namespace, brain_owner uses it."""
        from runtime.tasks.handlers.brain_ingest import handle_brain_ingest

        mock_response = MagicMock()
        mock_response.data = [{"id": "chunk-ns-001"}]

        inserted_row = {}

        def capture_insert(row):
            inserted_row.update(row)
            mock_q = MagicMock()
            mock_q.execute.return_value = mock_response
            return mock_q

        mock_entities_resp = MagicMock()
        mock_entities_resp.data = []
        mock_entities_q = MagicMock()
        mock_entities_q.select.return_value = mock_entities_q
        mock_entities_q.eq.return_value = mock_entities_q
        mock_entities_q.execute.return_value = mock_entities_resp

        mock_sb = MagicMock()

        def table_router(name):
            if name == "brain_entities":
                return mock_entities_q
            mock_q = MagicMock()
            mock_q.insert.side_effect = capture_insert
            return mock_q

        mock_sb.table.side_effect = table_router

        task = {
            "id": "task-ns-001",
            "client_id": "sparkle-internal",
            "payload": {
                "content": "Zenya is the first character, born from 800 files of collective creation.",
                "source_agent": "seed",
                "ingest_type": "seed",
                "target_namespace": "sparkle-lore",
            },
        }

        with patch("runtime.tasks.handlers.brain_ingest.supabase", mock_sb):
            with patch(
                "runtime.tasks.handlers.brain_ingest.get_embedding",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await handle_brain_ingest(task)

        assert "Anotado no Brain" in result["message"]
        assert inserted_row.get("brain_owner") == "sparkle-lore"
