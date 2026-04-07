"""
Tests for W0-BRAIN-1: Brain Namespace Enforcement.

Validates:
- SEMANTIC_NAMESPACES and SYSTEM_NAMESPACES constants exist
- resolve_namespace() falls back to 'general' for unknown semantic namespaces
- resolve_namespace() accepts valid semantic namespaces
- resolve_namespace() accepts client-{id} pattern
- is_valid_namespace() helper
"""
from __future__ import annotations

import logging
import pytest

from runtime.brain.namespace import (
    SEMANTIC_NAMESPACES,
    SYSTEM_NAMESPACES,
    is_valid_namespace,
    resolve_namespace,
)


# ── AC-1: Constants exist and contain expected values ──────────────────────

class TestNamespaceConstants:
    def test_semantic_namespaces_exist(self):
        assert SEMANTIC_NAMESPACES is not None
        assert len(SEMANTIC_NAMESPACES) > 0

    def test_semantic_namespaces_contains_sparkle_lore(self):
        assert "sparkle-lore" in SEMANTIC_NAMESPACES

    def test_semantic_namespaces_contains_mauro_personal(self):
        assert "mauro-personal" in SEMANTIC_NAMESPACES

    def test_semantic_namespaces_contains_sparkle_market(self):
        assert "sparkle-market" in SEMANTIC_NAMESPACES

    def test_system_namespaces_exist(self):
        assert SYSTEM_NAMESPACES is not None
        assert len(SYSTEM_NAMESPACES) > 0

    def test_system_namespaces_contains_expected(self):
        expected = {"youtube", "web", "file_pdf", "file_csv", "file_text",
                    "conversation", "client_dna", "insight", "general"}
        assert expected.issubset(SYSTEM_NAMESPACES)


# ── AC-2: Validation on ingestion ──────────────────────────────────────────

class TestResolveNamespaceValidation:
    def test_valid_semantic_namespace_accepted(self):
        result = resolve_namespace(metadata={"namespace": "sparkle-lore"})
        assert result == "sparkle-lore"

    def test_valid_semantic_namespace_mauro_personal(self):
        result = resolve_namespace(metadata={"namespace": "mauro-personal"})
        assert result == "mauro-personal"

    def test_valid_system_namespace_accepted(self):
        result = resolve_namespace(metadata={"namespace": "youtube"})
        assert result == "youtube"

    def test_unknown_semantic_namespace_falls_back_to_general(self, caplog):
        with caplog.at_level(logging.WARNING, logger="runtime.brain.namespace"):
            result = resolve_namespace(metadata={"namespace": "totally-unknown-ns"})
        assert result == "general"
        assert "Namespace desconhecido" in caplog.text
        assert "totally-unknown-ns" in caplog.text

    def test_client_namespace_pattern_accepted(self):
        result = resolve_namespace(metadata={"namespace": "client-abc123"})
        assert result == "client-abc123"

    def test_client_namespace_with_uuid_accepted(self):
        result = resolve_namespace(metadata={"namespace": "client-f47ac10b-58cc"})
        assert result == "client-f47ac10b-58cc"

    def test_no_namespace_falls_back_correctly(self):
        result = resolve_namespace(metadata={"source_type": "youtube"})
        assert result == "youtube"

    def test_empty_metadata_returns_general(self):
        result = resolve_namespace()
        assert result == "general"


# ── is_valid_namespace helper ───────────────────────────────────────────────

class TestIsValidNamespace:
    def test_semantic_namespace_is_valid(self):
        assert is_valid_namespace("sparkle-lore") is True
        assert is_valid_namespace("mauro-personal") is True

    def test_system_namespace_is_valid(self):
        assert is_valid_namespace("general") is True
        assert is_valid_namespace("youtube") is True

    def test_client_pattern_is_valid(self):
        assert is_valid_namespace("client-abc") is True
        assert is_valid_namespace("client-123") is True

    def test_unknown_namespace_is_invalid(self):
        assert is_valid_namespace("random-garbage") is False
        assert is_valid_namespace("not-a-namespace") is False
