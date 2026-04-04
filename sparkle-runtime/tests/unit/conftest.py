"""
Shared fixtures for Sparkle Runtime UNIT tests.

All external dependencies are mocked:
- Supabase (DB)
- Anthropic (Claude API)
- OpenAI (embeddings)
- Z-API (WhatsApp)
- Redis (ARQ)
- httpx (external HTTP calls)
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Environment variables for settings (before any import) ──────────────

@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """Set minimal env vars so Settings() doesn't fail."""
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MAURO_WHATSAPP", "5512999999999")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")


# ── Mock Supabase client ────────────────────────────────────────────────

class MockSupabaseResponse:
    """Simulates a Supabase query response."""
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class MockSupabaseQuery:
    """Chainable mock for supabase.table(...).select(...).eq(...)... pattern."""
    def __init__(self, data=None, count=None):
        self._data = data or []
        self._count = count

    def select(self, *args, **kwargs):
        return self

    def insert(self, row):
        # Return inserted row with a fake id
        if isinstance(row, dict):
            row.setdefault("id", "fake-task-id-001")
            self._data = [row]
        return self

    def update(self, data):
        return self

    def delete(self):
        return self

    def eq(self, col, val):
        return self

    def neq(self, col, val):
        return self

    def gt(self, col, val):
        return self

    def gte(self, col, val):
        return self

    def lt(self, col, val):
        return self

    def lte(self, col, val):
        return self

    def in_(self, col, vals):
        return self

    def ilike(self, col, val):
        return self

    def text_search(self, col, val):
        return self

    def order(self, col, **kwargs):
        return self

    def limit(self, n):
        return self

    def single(self):
        return self

    def execute(self):
        return MockSupabaseResponse(data=self._data, count=self._count)


class MockSupabaseClient:
    """Mock Supabase client with table() and rpc() support."""
    def __init__(self):
        self._table_data = {}  # table_name -> list of rows
        self._rpc_data = {}    # rpc_name -> response data

    def table(self, name):
        data = self._table_data.get(name, [])
        return MockSupabaseQuery(data=data)

    def rpc(self, name, params=None):
        data = self._rpc_data.get(name, [])
        return MockSupabaseQuery(data=data)

    def set_table_data(self, table_name, rows):
        self._table_data[table_name] = rows

    def set_rpc_data(self, rpc_name, rows):
        self._rpc_data[rpc_name] = rows


@pytest.fixture()
def mock_supabase():
    """Provides a MockSupabaseClient and patches runtime.db.supabase."""
    client = MockSupabaseClient()
    with patch("runtime.db.get_supabase", return_value=MagicMock()):
        yield client


# ── Mock LLM (call_claude) ──────────────────────────────────────────────

@pytest.fixture()
def mock_call_claude():
    """Patches runtime.utils.llm.call_claude to return controlled text."""
    with patch("runtime.utils.llm.call_claude", new_callable=AsyncMock) as m:
        m.return_value = "Mocked Claude response"
        yield m


# ── Mock httpx for embeddings and external calls ────────────────────────

@pytest.fixture()
def mock_httpx_openai_embedding():
    """Mocks httpx.AsyncClient to return a fake embedding from OpenAI."""
    fake_embedding = [0.1] * 1536  # text-embedding-3-small dimension

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [{"embedding": fake_embedding}]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        yield fake_embedding


# ── Mock Z-API ──────────────────────────────────────────────────────────

@pytest.fixture()
def mock_zapi():
    """Patches Z-API send_text and send_audio."""
    with patch("runtime.integrations.zapi.send_text") as send_text, \
         patch("runtime.integrations.zapi.send_audio") as send_audio:
        yield {"send_text": send_text, "send_audio": send_audio}


# ── FastAPI TestClient ──────────────────────────────────────────────────

@pytest.fixture()
def test_app():
    """
    Creates a FastAPI TestClient with all externals mocked.
    Use for endpoint-level tests.
    """
    # We need to patch before importing the app
    with patch("runtime.db.get_supabase") as mock_get_sb, \
         patch("runtime.db._create_client") as mock_create, \
         patch("runtime.scheduler.start_scheduler"), \
         patch("runtime.scheduler.stop_scheduler"):
        mock_sb = MockSupabaseClient()
        mock_get_sb.return_value = mock_sb
        mock_create.return_value = mock_sb

        from fastapi.testclient import TestClient
        from runtime.main import app
        with TestClient(app) as client:
            yield client, mock_sb
