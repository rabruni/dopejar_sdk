"""
platform_sdk.tier0_core.http
─────────────────────────────
HTTP primitives: standard status codes, response helpers, and typed response
envelopes. All services and agents share these constants so error codes are
consistent across the platform.

Minimal stack: DEFERRED — add when first HTTP framework integration is wired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


# ── Status code constants ──────────────────────────────────────────────────

class HTTP:
    """Standard HTTP status codes used across the platform."""

    # 2xx
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204

    # 3xx
    MOVED_PERMANENTLY = 301
    FOUND = 302
    NOT_MODIFIED = 304

    # 4xx
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    GONE = 410
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429

    # 5xx
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


# ── Response envelope ─────────────────────────────────────────────────────

@dataclass
class ApiResponse(Generic[T]):
    """Typed response envelope used by all platform APIs."""
    data: T | None = None
    error: str | None = None
    request_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "error": self.error,
            "request_id": self.request_id,
            "meta": self.meta,
        }


def ok(data: T, request_id: str | None = None, **meta: Any) -> ApiResponse[T]:
    """Return a successful ApiResponse."""
    return ApiResponse(data=data, request_id=request_id, meta=dict(meta))


def err(message: str, request_id: str | None = None, **meta: Any) -> ApiResponse[None]:
    """Return an error ApiResponse."""
    return ApiResponse(error=message, request_id=request_id, meta=dict(meta))


__all__ = ["HTTP", "ApiResponse", "ok", "err"]
