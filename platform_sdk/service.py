"""
platform_sdk.service
──────────────────────
Service surface — full platform import contract for backend services.

This is a strict *superset* of ``platform_sdk.agent``. AI-enabled services
that need both LLM capabilities AND service infrastructure (auth, DB, metrics,
etc.) should import from here — or from ``platform_sdk`` directly (same thing).

``platform_sdk.__init__`` re-exports everything from this module, so all
existing ``from platform_sdk import ...`` imports continue to work unchanged.

Usage::

    from platform_sdk.service import get_session, verify_token, complete
    # identical to:
    from platform_sdk import get_session, verify_token, complete
"""
from __future__ import annotations

# ── Agent surface (re-exported in full) ───────────────────────────────────────
from platform_sdk.agent import (
    complete,
    embed,
    Message,
    observe,
    get_llm_tracer,
    record_inference,
    vector_search,
    vector_upsert,
    vector_delete,
    get_logger,
    PlatformError,
    RateLimitError,
    UpstreamError,
)

# ── Identity & auth ───────────────────────────────────────────────────────────
from platform_sdk.tier0_core.identity import verify_token, get_principal, Principal

# ── Full error taxonomy ───────────────────────────────────────────────────────
from platform_sdk.tier0_core.errors import (
    AuthError,
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
)

# ── Config & secrets ──────────────────────────────────────────────────────────
from platform_sdk.tier0_core.config import get_config, PlatformConfig
from platform_sdk.tier0_core.secrets import get_secret, SecretStr

# ── Data ──────────────────────────────────────────────────────────────────────
from platform_sdk.tier0_core.data import get_session, get_engine

# ── Metrics ───────────────────────────────────────────────────────────────────
from platform_sdk.tier0_core.metrics import counter, gauge, histogram

# ── Context ───────────────────────────────────────────────────────────────────
from platform_sdk.tier1_runtime.context import get_context, set_context, RequestContext

# ── Validation & serialization ────────────────────────────────────────────────
from platform_sdk.tier1_runtime.validate import validate_input
from platform_sdk.tier1_runtime.serialize import serialize, deserialize

# ── Retry & rate limiting ─────────────────────────────────────────────────────
from platform_sdk.tier1_runtime.retry import retry_policy
from platform_sdk.tier1_runtime.ratelimit import check_rate_limit

# ── Reliability ───────────────────────────────────────────────────────────────
from platform_sdk.tier2_reliability.health import HealthChecker, get_health_checker
from platform_sdk.tier2_reliability.audit import audit, AuditRecord
from platform_sdk.tier2_reliability.cache import get_cache

# ── Platform services ─────────────────────────────────────────────────────────
from platform_sdk.tier3_platform.authorization import can, require_permission
from platform_sdk.tier3_platform.notifications import send_notification

# ── Middleware ────────────────────────────────────────────────────────────────
from platform_sdk.tier1_runtime.middleware import PlatformASGIMiddleware, PlatformWSGIMiddleware

__all__ = [
    # ── Agent surface (re-exported) ──────────────────────────────────────────
    # inference
    "complete", "embed", "Message",
    # llm_obs
    "observe", "get_llm_tracer", "record_inference",
    # vector
    "vector_search", "vector_upsert", "vector_delete",
    # logging
    "get_logger",
    # errors (agent subset)
    "PlatformError", "RateLimitError", "UpstreamError",
    # ── Service-only additions ───────────────────────────────────────────────
    # identity
    "verify_token", "get_principal", "Principal",
    # errors (full set)
    "AuthError", "ValidationError", "NotFoundError", "ForbiddenError", "ConflictError",
    # config
    "get_config", "PlatformConfig",
    # secrets
    "get_secret", "SecretStr",
    # data
    "get_session", "get_engine",
    # metrics
    "counter", "gauge", "histogram",
    # context
    "get_context", "set_context", "RequestContext",
    # validate
    "validate_input",
    # serialize
    "serialize", "deserialize",
    # retry
    "retry_policy",
    # ratelimit
    "check_rate_limit",
    # health
    "HealthChecker", "get_health_checker",
    # audit
    "audit", "AuditRecord",
    # cache
    "get_cache",
    # authorization
    "can", "require_permission",
    # notifications
    "send_notification",
    # middleware
    "PlatformASGIMiddleware", "PlatformWSGIMiddleware",
]
