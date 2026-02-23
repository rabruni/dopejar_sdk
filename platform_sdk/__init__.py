"""
platform_sdk
────────────
Stable top-level exports. Import from here, not from sub-modules directly.
Every name exported here is part of the public API and subject to semver.
"""
from platform_sdk.tier0_core.identity import verify_token, get_principal, Principal
from platform_sdk.tier0_core.logging import get_logger
from platform_sdk.tier0_core.errors import (
    PlatformError,
    AuthError,
    ValidationError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
)
from platform_sdk.tier0_core.config import get_config, PlatformConfig
from platform_sdk.tier0_core.secrets import get_secret, SecretStr
from platform_sdk.tier0_core.data import get_session, get_engine
from platform_sdk.tier0_core.metrics import counter, gauge, histogram

from platform_sdk.tier1_runtime.context import (
    get_context,
    set_context,
    RequestContext,
)
from platform_sdk.tier1_runtime.validate import validate_input
from platform_sdk.tier1_runtime.serialize import serialize, deserialize
from platform_sdk.tier1_runtime.retry import retry_policy
from platform_sdk.tier1_runtime.ratelimit import check_rate_limit

from platform_sdk.tier2_reliability.health import HealthChecker, get_health_checker
from platform_sdk.tier2_reliability.audit import audit, AuditRecord
from platform_sdk.tier2_reliability.cache import get_cache

from platform_sdk.tier3_platform.authorization import can, require_permission
from platform_sdk.tier3_platform.notifications import send_notification
from platform_sdk.tier3_platform.vector import vector_search, vector_upsert, vector_delete

from platform_sdk.tier4_advanced.inference import complete, embed, Message
from platform_sdk.tier4_advanced.llm_obs import observe, get_llm_tracer, record_inference
from platform_sdk.tier1_runtime.middleware import PlatformASGIMiddleware, PlatformWSGIMiddleware

__version__ = "0.1.0"
__all__ = [
    # identity
    "verify_token", "get_principal", "Principal",
    # logging
    "get_logger",
    # errors
    "PlatformError", "AuthError", "ValidationError",
    "NotFoundError", "RateLimitError", "UpstreamError",
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
    # vector
    "vector_search", "vector_upsert", "vector_delete",
    # inference
    "complete", "embed", "Message",
    # llm_obs
    "observe", "get_llm_tracer", "record_inference",
    # middleware
    "PlatformASGIMiddleware", "PlatformWSGIMiddleware",
]
