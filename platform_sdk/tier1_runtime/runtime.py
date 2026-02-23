"""
platform_sdk.tier1_runtime.runtime
────────────────────────────────────
Runtime environment detection and build metadata. Provides a stable interface
to know: what environment are we running in, what version is deployed, and
what service is this. Used by logging, metrics, and tracing to attach standard
labels to every signal.

Minimal stack: DEFERRED — add when multi-environment deployment is wired.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

Env = Literal["local", "test", "staging", "production", "unknown"]


@dataclass(frozen=True)
class RuntimeInfo:
    """Immutable snapshot of the current runtime environment."""
    service_name: str
    environment: Env
    version: str
    commit_sha: str
    region: str
    instance_id: str


@lru_cache(maxsize=1)
def get_runtime() -> RuntimeInfo:
    """
    Return the current RuntimeInfo, inferred from environment variables.

    Expected env vars (set by your deployment platform):
      PLATFORM_SERVICE_NAME   — e.g. "api-gateway"
      PLATFORM_ENVIRONMENT    — local | test | staging | production
      PLATFORM_VERSION        — e.g. "1.4.2"
      PLATFORM_COMMIT_SHA     — git commit hash
      PLATFORM_REGION         — e.g. "us-east-1"
      PLATFORM_INSTANCE_ID    — pod/container/instance ID
    """
    raw_env = os.environ.get("PLATFORM_ENVIRONMENT", "local").lower()
    env: Env
    if raw_env in ("local", "test", "staging", "production"):
        env = raw_env  # type: ignore[assignment]
    else:
        env = "unknown"

    return RuntimeInfo(
        service_name=os.environ.get("PLATFORM_SERVICE_NAME", "unknown"),
        environment=env,
        version=os.environ.get("PLATFORM_VERSION", "0.0.0-dev"),
        commit_sha=os.environ.get("PLATFORM_COMMIT_SHA", "unknown"),
        region=os.environ.get("PLATFORM_REGION", "local"),
        instance_id=os.environ.get("PLATFORM_INSTANCE_ID", "local"),
    )


def is_production() -> bool:
    return get_runtime().environment == "production"


def is_test() -> bool:
    return get_runtime().environment == "test"


def is_local() -> bool:
    return get_runtime().environment == "local"


__all__ = ["RuntimeInfo", "Env", "get_runtime", "is_production", "is_test", "is_local"]
