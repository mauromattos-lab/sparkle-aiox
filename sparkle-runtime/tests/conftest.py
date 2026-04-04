"""
Shared fixtures for Sparkle Runtime integration tests.

These tests run against the LIVE runtime at https://runtime.sparkleai.tech
They are NOT mocked — they hit real endpoints and real Supabase.
"""
from __future__ import annotations

import os

import httpx
import pytest

BASE_URL = os.environ.get("RUNTIME_BASE_URL", "https://runtime.sparkleai.tech")


@pytest.fixture()
async def client():
    """Per-test async HTTP client — avoids stale connection issues."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as c:
        yield c
