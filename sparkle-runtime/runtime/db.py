"""
Supabase client pool — thread-safe access for asyncio.to_thread() workers.

BLOCK-08 FIX: httpx.Client (used internally by supabase-py) is NOT
thread-safe.  The runtime dispatches DB calls via asyncio.to_thread(),
so 7+ parallel tasks sharing a single Client caused 502 errors.

Solution: thread-local storage gives each worker thread its own Supabase
client instance.  A transparent proxy (`supabase`) ensures that existing
code like `from runtime.db import supabase` keeps working unchanged —
every attribute access is routed to the calling thread's client.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

from runtime.config import settings

logger = logging.getLogger(__name__)

_POSTGREST_TIMEOUT = 15  # seconds — generous for heavy queries
_local = threading.local()


def _create_client() -> Client:
    """Create a fresh Supabase client with tuned timeout settings."""
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

    opts = SyncClientOptions(
        postgrest_client_timeout=_POSTGREST_TIMEOUT,
    )
    return create_client(settings.supabase_url, settings.supabase_key, options=opts)


def get_supabase() -> Client:
    """Return a thread-local Supabase client (created lazily).

    Safe to call from any thread — each thread gets its own httpx.Client
    under the hood, avoiding the thread-safety issue that caused BLOCK-08.
    """
    client: Client | None = getattr(_local, "client", None)
    if client is None:
        client = _create_client()
        _local.client = client
        logger.debug(
            "Created Supabase client for thread %s",
            threading.current_thread().name,
        )
    return client


class _ThreadLocalSupabaseProxy:
    """Transparent proxy that delegates every access to a thread-local client.

    Existing code does:
        from runtime.db import supabase
        await asyncio.to_thread(lambda: supabase.table("x").select("*").execute())

    The lambda captures `supabase` (this proxy).  When the lambda runs in the
    worker thread, `supabase.table(...)` hits __getattr__ which calls
    get_supabase() — returning that thread's own Client.  Thread-safe.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_supabase(), name)

    def __repr__(self) -> str:
        return f"<ThreadLocalSupabaseProxy -> {get_supabase()!r}>"


# ---------------------------------------------------------------------------
# Module-level export — drop-in replacement for the old singleton.
# All 45+ files that do `from runtime.db import supabase` keep working.
# ---------------------------------------------------------------------------
supabase: Client = _ThreadLocalSupabaseProxy()  # type: ignore[assignment]
