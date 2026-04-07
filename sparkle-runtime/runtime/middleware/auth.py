"""
API key authentication middleware for Sparkle Runtime.

Protects ALL endpoints via X-API-Key header, except public and webhook paths.
If RUNTIME_API_KEY is not configured, protected requests are rejected (fail-closed).
"""
from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from runtime.config import settings

logger = logging.getLogger(__name__)

# Webhook paths — open regardless of auth (validated separately, e.g. Asaas token)
EXEMPT_PATHS: set[str] = {
    "/friday/webhook",
    "/debug/webhook",
}

EXEMPT_PREFIXES: tuple[str, ...] = (
    "/zenya/webhook/",
    "/billing/webhook/",
)

# Public paths — no auth required for any method
PUBLIC_PATHS: set[str] = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}

PUBLIC_PREFIXES: tuple[str, ...] = (
    "/docs/",
)


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def _is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header on all non-public, non-exempt requests."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Webhooks — pass through (they have their own auth)
        if _is_exempt(path):
            return await call_next(request)

        # Public endpoints — always accessible
        if _is_public(path):
            return await call_next(request)

        api_key = settings.runtime_api_key

        # Fail-closed: no key configured means reject protected requests
        if not api_key:
            if not getattr(self, "_warned", False):
                logger.warning(
                    "RUNTIME_API_KEY is not set — protected requests will be rejected. "
                    "Set this env var to allow authenticated access."
                )
                self._warned = True  # type: ignore[attr-defined]
            return JSONResponse(
                status_code=503,
                content={"detail": "API key not configured — set RUNTIME_API_KEY"},
            )

        # Validate key
        provided = request.headers.get("X-API-Key", "")
        if provided != api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
