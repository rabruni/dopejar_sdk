"""
platform_sdk.tier1_runtime.context
────────────────────────────────────
Request context — correlation IDs, principal context, propagation
across async boundaries into logs, metrics, and traces.

Uses Python contextvars for async-safe, framework-agnostic storage.
Automatically propagated by logging.py via structlog contextvars.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


# ── Domain model ─────────────────────────────────────────────────────────────

@dataclass
class RequestContext:
    """All per-request metadata available throughout the request lifecycle."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None
    principal_id: str | None = None
    org_id: str | None = None
    service: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── ContextVar storage ────────────────────────────────────────────────────────

_ctx: ContextVar[RequestContext] = ContextVar(
    "platform_request_context",
    default=RequestContext(),
)


# ── Public API ────────────────────────────────────────────────────────────────

def get_context() -> RequestContext:
    """Return the current request context."""
    return _ctx.get()


def set_context(ctx: RequestContext) -> None:
    """Set the request context for the current async scope."""
    _ctx.set(ctx)
    # Sync with structlog contextvars so all log calls get these fields
    try:
        import structlog
        structlog.contextvars.bind_contextvars(
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
            principal_id=ctx.principal_id,
            org_id=ctx.org_id,
        )
    except ImportError:
        pass


def new_context(
    principal_id: str | None = None,
    org_id: str | None = None,
    trace_id: str | None = None,
    **metadata: Any,
) -> RequestContext:
    """Create and activate a new request context. Returns the new context."""
    ctx = RequestContext(
        principal_id=principal_id,
        org_id=org_id,
        trace_id=trace_id,
        metadata=metadata,
    )
    set_context(ctx)
    return ctx


def get_request_id() -> str:
    return get_context().request_id


def get_principal_id() -> str | None:
    return get_context().principal_id


def get_org_id() -> str | None:
    return get_context().org_id


__sdk_export__ = {
    "surface": "service",
    "exports": ["get_context", "set_context", "RequestContext"],
    "description": "Request context via contextvars (request_id, trace_id, principal)",
    "tier": "tier1_runtime",
    "module": "context",
}
