"""
platform_sdk.tier0_core.logging
────────────────────────────────
Structured logs with levels, automatic context injection (request_id,
trace_id, principal_id), redaction, and sink routing.

Minimal stack: structlog + Grafana Loki (or stdout JSON)
Configure via: PLATFORM_LOG_LEVEL, PLATFORM_LOG_FORMAT=json|console
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


# ── Configuration ─────────────────────────────────────────────────────────────

def _configure_structlog() -> None:
    log_level = os.getenv("PLATFORM_LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("PLATFORM_LOG_FORMAT", "json").lower()

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _redact_processor,
    ]

    if log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))


# ── Redaction processor ───────────────────────────────────────────────────────

_REDACT_KEYS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "auth", "credential", "private_key", "access_token",
    "refresh_token", "client_secret", "ssn", "credit_card",
})

_REDACTED = "[REDACTED]"


def _redact_processor(
    logger: Any, method: str, event_dict: dict
) -> dict:
    """Strip sensitive fields from log records before output."""
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


# ── Public API ────────────────────────────────────────────────────────────────

_configured = False


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Return a structured logger bound to the given name.

    Usage:
        log = get_logger(__name__)
        log.info("user.login", user_id="u_123", provider="github")
        log.error("payment.failed", order_id="o_456", reason="card_declined")
    """
    global _configured
    if not _configured:
        _configure_structlog()
        _configured = True
    return structlog.get_logger(name or __name__)


def bind_context(**kwargs: Any) -> None:
    """
    Bind key-value pairs to the current async/thread context.
    All subsequent log calls in this context will include these fields.

    Usage (in middleware):
        bind_context(request_id="req_abc", user_id="u_123")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all context-bound log fields. Call at end of request."""
    structlog.contextvars.clear_contextvars()
