"""
platform_sdk.tier0_core.redact
───────────────────────────────
PII and secret redaction utilities. Provides field-level redaction for
structured data, regex-based pattern scrubbing, and a structlog processor
that automatically redacts sensitive keys before log emission.

All logging and audit pipelines pass through redact to prevent credential
leakage to log aggregators.

Minimal stack: DEFERRED — add when PII compliance requirements are specified.
"""
from __future__ import annotations

import re
from typing import Any

# ── Default redacted key names (case-insensitive) ─────────────────────────

_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_token", "refresh_token", "private_key", "client_secret",
    "authorization", "x-api-key", "cookie", "session", "ssn",
    "credit_card", "card_number", "cvv", "pin",
})

# ── Regex patterns for inline scrubbing ───────────────────────────────────

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I), "Bearer [REDACTED]"),
    # Basic auth
    (re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.I), "Basic [REDACTED]"),
    # Generic key=value secrets
    (re.compile(
        r"(password|secret|token|api[_-]?key)\s*=\s*[^\s&\"']+",
        re.I,
    ), r"\1=[REDACTED]"),
]

REDACTED = "[REDACTED]"


# ── Public API ─────────────────────────────────────────────────────────────

def redact_dict(
    data: dict[str, Any],
    sensitive_keys: frozenset[str] | None = None,
    *,
    deep: bool = True,
) -> dict[str, Any]:
    """
    Return a copy of *data* with sensitive key values replaced by REDACTED.
    If *deep* is True, recurse into nested dicts and lists.
    """
    keys = sensitive_keys if sensitive_keys is not None else _SENSITIVE_KEYS
    result: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in keys:
            result[k] = REDACTED
        elif deep and isinstance(v, dict):
            result[k] = redact_dict(v, keys, deep=True)
        elif deep and isinstance(v, list):
            result[k] = [
                redact_dict(item, keys, deep=True) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[k] = v
    return result


def scrub_string(text: str) -> str:
    """Apply regex-based scrubbing to an arbitrary string."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def structlog_redact_processor(
    logger: Any,
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    structlog processor that redacts sensitive keys from the event dict.
    Add to the structlog processor chain before any serialisation step.
    """
    return redact_dict(event_dict)


__all__ = [
    "REDACTED",
    "redact_dict",
    "scrub_string",
    "structlog_redact_processor",
    "_SENSITIVE_KEYS",
]
