"""
Rate limiting middleware for Sparkle Runtime.

Strategy: sliding-window in-memory (single dict per tier).
Redis can replace this later by swapping _RateLimiter with a Redis-backed version.

Tiers:
  GLOBAL  — 120 req/min per IP   (all endpoints not otherwise exempted)
  STRICT  — 10  req/min per IP   (AI-heavy endpoints that call Anthropic/OpenAI)

Exempt paths (time-sensitive webhooks that must never be throttled):
  /health
  /friday/webhook
  /zenya/webhook/*
"""
from __future__ import annotations

import asyncio
import ipaddress
import time
from collections import deque
from typing import Deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GLOBAL_LIMIT = 120   # requests
STRICT_LIMIT = 10    # requests
WINDOW_SECONDS = 60  # sliding window width

# AI-heavy endpoints that get the strict budget
STRICT_PATHS: frozenset[str] = frozenset(
    [
        "/content/generate",
        "/content/generate-batch",
        "/brain/ingest/url",
        "/brain/ingest/file",
        "/onboarding/start",
        "/agent/activate",
    ]
)

# Prefix-based strict paths (e.g. /brain/pipeline/*)
STRICT_PREFIXES: tuple[str, ...] = ("/brain/pipeline/",)

# Paths that bypass rate limiting entirely
EXEMPT_PATHS: frozenset[str] = frozenset(["/health"])

# Prefix-based exemptions
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/friday/webhook",
    "/zenya/webhook/",
)

# How often the background task purges stale window entries (seconds)
CLEANUP_INTERVAL = 60


# ---------------------------------------------------------------------------
# Sliding-window rate limiter (in-memory)
# ---------------------------------------------------------------------------

class _RateLimiter:
    """
    Per-IP sliding window tracker.
    Stores a deque of request timestamps for each (ip, tier) key.
    """

    def __init__(self) -> None:
        # key: (ip_address, tier_str) → deque of float timestamps
        self._windows: dict[tuple[str, str], Deque[float]] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(
        self, ip: str, tier: str, limit: int
    ) -> tuple[bool, int]:
        """
        Check if the request is within the rate limit.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS
        key = (ip, tier)

        async with self._lock:
            dq = self._windows.setdefault(key, deque())

            # Evict timestamps outside the sliding window
            while dq and dq[0] <= cutoff:
                dq.popleft()

            if len(dq) >= limit:
                # How many seconds until the oldest entry expires
                retry_after = int(WINDOW_SECONDS - (now - dq[0])) + 1
                return False, retry_after

            dq.append(now)
            return True, 0

    async def cleanup(self) -> None:
        """Remove fully-expired windows to bound memory usage."""
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS

        async with self._lock:
            stale_keys = [
                k for k, dq in self._windows.items()
                if not dq or dq[-1] <= cutoff
            ]
            for k in stale_keys:
                del self._windows[k]


# Module-level singleton shared across all requests
_limiter = _RateLimiter()


# ---------------------------------------------------------------------------
# Background cleanup task
# ---------------------------------------------------------------------------

async def _cleanup_loop() -> None:  # pragma: no cover
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        await _limiter.cleanup()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

TRUSTED_PROXIES = {
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
}


def _is_trusted_proxy(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in TRUSTED_PROXIES)
    except ValueError:
        return False


def _get_client_ip(request: Request) -> str:
    """
    Resolve the real client IP.
    Only trust X-Forwarded-For when the direct connection comes from a trusted proxy.
    """
    client_ip = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(client_ip):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return client_ip


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def _is_strict(method: str, path: str) -> bool:
    if method.upper() != "POST":
        return False
    if path in STRICT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in STRICT_PREFIXES)


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that enforces per-IP rate limits.

    Mount this BEFORE auth middleware so that bad actors are rejected
    cheaply without touching auth logic or database.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method

        # 1. Exempt paths — pass through immediately
        if _is_exempt(path):
            return await call_next(request)

        ip = _get_client_ip(request)

        # 2. Strict tier check (AI-heavy endpoints)
        if _is_strict(method, path):
            allowed, retry_after = await _limiter.is_allowed(ip, "strict", STRICT_LIMIT)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Rate limit exceeded. Try again in {retry_after} seconds"
                        )
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        # 3. Global tier check (all non-exempt endpoints)
        allowed, retry_after = await _limiter.is_allowed(ip, "global", GLOBAL_LIMIT)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded. Try again in {retry_after} seconds"
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Startup helper — call from FastAPI lifespan
# ---------------------------------------------------------------------------

def start_cleanup_task() -> asyncio.Task:
    """Schedule the background cleanup loop. Must be called inside an async context."""
    return asyncio.create_task(_cleanup_loop())
