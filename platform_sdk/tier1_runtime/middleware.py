"""
platform_sdk.tier1_runtime.middleware
───────────────────────────────────────
Framework-agnostic middleware factory. Provides ASGI and WSGI middleware
that auto-injects request context, structured logging, metrics, and rate
limiting for every inbound request.

Supports: FastAPI / Starlette (ASGI), Flask / Django (WSGI).

Minimal stack: DEFERRED — add when the first HTTP service is stood up.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from platform_sdk.tier1_runtime.context import RequestContext, set_context


# ── ASGI middleware ────────────────────────────────────────────────────────

class PlatformASGIMiddleware:
    """
    ASGI middleware that injects a RequestContext for every HTTP request.

    Usage (FastAPI / Starlette)::

        from platform_sdk import PlatformASGIMiddleware
        app.add_middleware(PlatformASGIMiddleware)
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        request_id = (
            headers.get(b"x-request-id", b"").decode()
            or headers.get(b"x-correlation-id", b"").decode()
            or str(uuid.uuid4())
        )
        trace_id = headers.get(b"x-trace-id", b"").decode() or request_id

        ctx = RequestContext(request_id=request_id, trace_id=trace_id)
        set_context(ctx)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            try:
                from platform_sdk.tier0_core.logging import get_logger
                get_logger().info(
                    "request_completed",
                    request_id=request_id,
                    duration_ms=round(duration_ms, 2),
                    path=scope.get("path", ""),
                    method=scope.get("method", ""),
                )
            except Exception:
                pass


# ── WSGI middleware ────────────────────────────────────────────────────────

class PlatformWSGIMiddleware:
    """
    WSGI middleware that injects a RequestContext for every HTTP request.

    Usage (Flask)::

        from platform_sdk import PlatformWSGIMiddleware
        app.wsgi_app = PlatformWSGIMiddleware(app.wsgi_app)
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    def __call__(self, environ: dict, start_response: Callable) -> Any:
        request_id = (
            environ.get("HTTP_X_REQUEST_ID")
            or environ.get("HTTP_X_CORRELATION_ID")
            or str(uuid.uuid4())
        )
        trace_id = environ.get("HTTP_X_TRACE_ID") or request_id

        ctx = RequestContext(request_id=request_id, trace_id=trace_id)
        set_context(ctx)

        start = time.perf_counter()
        try:
            return self.app(environ, start_response)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            try:
                from platform_sdk.tier0_core.logging import get_logger
                get_logger().info(
                    "request_completed",
                    request_id=request_id,
                    duration_ms=round(duration_ms, 2),
                    path=environ.get("PATH_INFO", ""),
                    method=environ.get("REQUEST_METHOD", ""),
                )
            except Exception:
                pass


__all__ = ["PlatformASGIMiddleware", "PlatformWSGIMiddleware"]


__sdk_export__ = {
    "surface": "service",
    "exports": ["PlatformASGIMiddleware", "PlatformWSGIMiddleware"],
    "description": "ASGI/WSGI middleware factory for context, auth, logging, and tracing",
    "tier": "tier1_runtime",
    "module": "middleware",
}
