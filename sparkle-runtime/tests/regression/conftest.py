"""
Shared fixtures for Sparkle Runtime REGRESSION tests.

Reuses unit-test mock infrastructure (MockSupabaseClient, env vars, etc.)
so that regression tests run fully offline — no real Supabase, Claude, or Z-API.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Environment variables (must be set before any runtime import) ──────────

@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """Set minimal env vars so Settings() does not fail."""
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MAURO_WHATSAPP", "5512999999999")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")


# ── Mock Supabase (replicates unit conftest pattern) ──────────────────────

class MockSupabaseResponse:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class MockSupabaseQuery:
    """Chainable mock for supabase.table(...).select(...).eq(...) pattern."""

    def __init__(self, data=None, count=None):
        self._data = data or []
        self._count = count

    # Chainable methods
    def select(self, *a, **kw):   return self
    def insert(self, row):
        if isinstance(row, dict):
            row.setdefault("id", "fake-id-001")
            self._data = [row]
        return self
    def update(self, data):       return self
    def delete(self):             return self
    def eq(self, *a):             return self
    def neq(self, *a):            return self
    def gt(self, *a):             return self
    def gte(self, *a):            return self
    def lt(self, *a):             return self
    def lte(self, *a):            return self
    def in_(self, *a):            return self
    def ilike(self, *a):          return self
    def text_search(self, *a):    return self
    def or_(self, *a):            return self
    def contains(self, *a):       return self
    def order(self, *a, **kw):    return self
    def limit(self, n):           return self
    def single(self):             return self
    def maybe_single(self):       return self
    def execute(self):            return MockSupabaseResponse(data=self._data, count=self._count)


class MockSupabaseClient:
    def __init__(self):
        self._table_data: dict[str, list] = {}
        self._rpc_data: dict[str, list] = {}

    def table(self, name: str):
        data = self._table_data.get(name, [])
        return MockSupabaseQuery(data=data)

    def rpc(self, name: str, params=None):
        data = self._rpc_data.get(name, [])
        return MockSupabaseQuery(data=data)

    def set_table_data(self, table_name: str, rows: list):
        self._table_data[table_name] = rows

    def set_rpc_data(self, rpc_name: str, rows: list):
        self._rpc_data[rpc_name] = rows


# ── FastAPI TestClient fixture ────────────────────────────────────────────

@pytest.fixture()
def app_client():
    """
    Creates a FastAPI TestClient with all externals mocked.
    Yields (client, mock_supabase) tuple.
    """
    with patch("runtime.db.get_supabase") as mock_get_sb, \
         patch("runtime.db._create_client") as mock_create, \
         patch("runtime.scheduler.start_scheduler"), \
         patch("runtime.scheduler.stop_scheduler"):
        mock_sb = MockSupabaseClient()
        mock_get_sb.return_value = mock_sb
        mock_create.return_value = mock_sb

        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app) as client:
            yield client, mock_sb


# ── Mock LLM fixture ─────────────────────────────────────────────────────

@pytest.fixture()
def mock_call_claude():
    with patch("runtime.utils.llm.call_claude", new_callable=AsyncMock) as m:
        m.return_value = "Mocked Claude response"
        yield m
