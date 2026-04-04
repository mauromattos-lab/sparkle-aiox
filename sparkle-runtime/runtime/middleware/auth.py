"""
API key authentication middleware for Sparkle Runtime.

Protects all mutating endpoints (POST/PUT/DELETE) via X-API-Key header.
Read-only (GET) requests and webhook paths are exempt.
"""
from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from runtime.config import settings

logger = logging.getLogger(__name__)

# Paths that must remain open regardless of HTTP method
EXEMPT_PATHS: set[str] = {
    "/friday/webhook",
    "/debug/webhook",
}

# Prefix-based exemptions (e.g. /zenya/webhook/<client_id>)
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/zenya/webhook/",
)

# Methods that require auth
PROTECTED_METHODS: set[str] = {"POST", "PUT", "DELETE", "PATCH"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header on all mutating requests."""

    async def dispatch(self, request: Request, call_next) -> Response:
        api_key = settings.runtime_api_key

        # If no key is configured, warn once and pass all requests through
        if not api_key:
            if not getattr(self, "_warned", False):
                logger.warning(
                    "RUNTIME_API_KEY is not set — all requests are allowed. "
                    "Set this env var in production to protect the API."
                )
                self._warned = True  # type: ignore[attr-defined]
            return await call_next(request)

        method = request.method.upper()

        # GET (and HEAD/OPTIONS) are always allowed
        if method not in PROTECTED_METHODS:
            return await call_next(request)

        path = request.url.path

        # Exempt specific paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Exempt prefix-matched paths
        if path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        # Validate key
        provided = request.headers.get("X-API-Key", "")
        if provided != api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
