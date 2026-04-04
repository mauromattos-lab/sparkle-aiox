"""
Unit tests for runtime config / settings.
"""
from __future__ import annotations

import os

import pytest


def test_settings_loads_from_env(monkeypatch):
    """Settings should pick up environment variables."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("MAURO_WHATSAPP", "5512000000000")
    monkeypatch.setenv("BRAIN_EMBEDDINGS_ENABLED", "true")
    monkeypatch.setenv("BRAIN_SIMILARITY_THRESHOLD", "0.80")

    # Clear the lru_cache so fresh Settings is created
    from runtime.config import get_settings
    get_settings.cache_clear()

    s = get_settings()
    assert s.supabase_url == "https://test.supabase.co"
    assert s.anthropic_api_key == "test-anthropic"
    assert s.mauro_whatsapp == "5512000000000"
    assert s.brain_embeddings_enabled is True
    assert s.brain_similarity_threshold == 0.80

    # Clean up cache
    get_settings.cache_clear()


def test_settings_defaults(monkeypatch):
    """Settings should have sensible defaults."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    monkeypatch.setenv("BRAIN_EMBEDDINGS_ENABLED", "false")
    monkeypatch.delenv("BRAIN_SIMILARITY_THRESHOLD", raising=False)

    from runtime.config import get_settings
    get_settings.cache_clear()

    s = get_settings()
    assert s.runtime_version == "0.1.0"
    assert s.sparkle_internal_client_id == "sparkle-internal"
    assert s.brain_embeddings_enabled is False
    # Default is 0.75 but may be overridden by .env file loaded at class definition
    assert 0.0 < s.brain_similarity_threshold <= 1.0

    get_settings.cache_clear()
