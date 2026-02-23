"""
platform_sdk.tier0_core.errors
───────────────────────────────
Standard error taxonomy, error codes, user-safe messages, and optional
Sentry/OTel error capture. Raising a PlatformError here automatically
reports it if an error backend is configured.

Minimal stack: Sentry OSS + OTel error signals
Select via:    PLATFORM_ERROR_BACKEND=sentry|otel|none
"""
from __future__ import annotations

import os
from typing import Any


# ── Base error ────────────────────────────────────────────────────────────────

class PlatformError(Exception):
    """
    Base class for all platform errors. Every error has:
    - code: stable machine-readable string (snake_case)
    - user_message: safe to surface to end users
    - detail: internal context, never shown to users
    - status_code: HTTP status code for API responses
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        code: str | None = None,
        user_message: str = "An unexpected error occurred.",
        detail: str | None = None,
        **metadata: Any,
    ) -> None:
        self.code = code or self.__class__.code
        self.user_message = user_message
        self.detail = detail or user_message
        self.metadata = metadata
        super().__init__(self.detail)
        _capture(self)

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.user_message,
            }
        }


# ── Typed error classes ───────────────────────────────────────────────────────

class AuthError(PlatformError):
    """Authentication or authorization failure."""
    status_code = 401
    code = "auth_error"


class ForbiddenError(PlatformError):
    """Principal is authenticated but not authorized for this action."""
    status_code = 403
    code = "forbidden"


class ValidationError(PlatformError):
    """Input validation failure."""
    status_code = 422
    code = "validation_error"

    def __init__(
        self,
        code: str | None = None,
        user_message: str = "Validation failed.",
        fields: dict | None = None,
        **metadata: Any,
    ) -> None:
        self.fields = fields or {}
        super().__init__(code, user_message, **metadata)

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.fields:
            d["error"]["fields"] = self.fields
        return d


class NotFoundError(PlatformError):
    """Requested resource does not exist."""
    status_code = 404
    code = "not_found"


class ConflictError(PlatformError):
    """Resource state conflict (e.g., duplicate creation)."""
    status_code = 409
    code = "conflict"


class RateLimitError(PlatformError):
    """Rate limit or quota exceeded."""
    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(
        self,
        code: str | None = None,
        user_message: str = "Too many requests. Please try again later.",
        retry_after: int | None = None,
        **metadata: Any,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(code, user_message, **metadata)


class UpstreamError(PlatformError):
    """Upstream service failure."""
    status_code = 502
    code = "upstream_error"


class ConfigurationError(PlatformError):
    """Misconfiguration detected at startup."""
    status_code = 500
    code = "configuration_error"


# ── Error capture backend ─────────────────────────────────────────────────────

def _capture(error: PlatformError) -> None:
    """Send error to configured backend. Called automatically by PlatformError.__init__."""
    backend = os.getenv("PLATFORM_ERROR_BACKEND", "none").lower()
    if backend == "none":
        return
    if backend == "sentry":
        _capture_sentry(error)
    elif backend == "otel":
        _capture_otel(error)


def _capture_sentry(error: PlatformError) -> None:
    try:
        import sentry_sdk
        if error.status_code >= 500:
            sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_message(
                str(error),
                level="warning",
                extras={"code": error.code, **error.metadata},
            )
    except ImportError:
        pass


def _capture_otel(error: PlatformError) -> None:
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        span.record_exception(error)
        span.set_status(trace.StatusCode.ERROR, str(error))
    except Exception:
        pass


def configure_sentry(dsn: str, **kwargs: Any) -> None:
    """Initialize Sentry — call once at application startup."""
    import sentry_sdk
    sentry_sdk.init(dsn=dsn, **kwargs)
    os.environ["PLATFORM_ERROR_BACKEND"] = "sentry"


__sdk_export__ = {
    "surface": "both",
    "exports": [
        "PlatformError", "AuthError", "ValidationError", "NotFoundError",
        "ForbiddenError", "ConflictError", "RateLimitError", "UpstreamError",
        "ConfigurationError",
    ],
    "description": "Standard error taxonomy for all platform modules",
    "tier": "tier0_core",
    "module": "errors",
}
