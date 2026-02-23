"""
platform_sdk.tier0_core.flags
──────────────────────────────
Feature flags and kill-switches via OpenFeature abstraction. Lets services
toggle features without deploys, perform canary rollouts, and kill dangerous
paths instantly.

Backed by: Flagsmith (OSS), LaunchDarkly (enterprise), or env-var based mock.

Minimal stack: DEFERRED — add when ≥2 features need gated rollout.
"""
from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from platform_sdk.tier0_core.errors import ConfigurationError


# ── Protocol ───────────────────────────────────────────────────────────────

@runtime_checkable
class FlagsProvider(Protocol):
    """OpenFeature-compatible flags provider interface."""

    def is_enabled(
        self,
        flag_key: str,
        default: bool = False,
        context: dict[str, Any] | None = None,
    ) -> bool: ...

    def get_string(
        self,
        flag_key: str,
        default: str = "",
        context: dict[str, Any] | None = None,
    ) -> str: ...

    def get_number(
        self,
        flag_key: str,
        default: float = 0.0,
        context: dict[str, Any] | None = None,
    ) -> float: ...


# ── Env-var mock provider (works in tests and CI) ──────────────────────────

class EnvFlagsProvider:
    """
    Read flags from environment variables.
    PLATFORM_FLAG_<FLAG_KEY>=true|false|<string>|<number>
    """

    def is_enabled(
        self,
        flag_key: str,
        default: bool = False,
        context: dict[str, Any] | None = None,
    ) -> bool:
        env_key = f"PLATFORM_FLAG_{flag_key.upper().replace('-', '_')}"
        val = os.environ.get(env_key)
        if val is None:
            return default
        return val.lower() in ("1", "true", "yes", "on")

    def get_string(
        self,
        flag_key: str,
        default: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        env_key = f"PLATFORM_FLAG_{flag_key.upper().replace('-', '_')}"
        return os.environ.get(env_key, default)

    def get_number(
        self,
        flag_key: str,
        default: float = 0.0,
        context: dict[str, Any] | None = None,
    ) -> float:
        env_key = f"PLATFORM_FLAG_{flag_key.upper().replace('-', '_')}"
        val = os.environ.get(env_key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default


class MockFlagsProvider:
    """In-memory provider for tests — seed flags via constructor."""

    def __init__(self, flags: dict[str, Any] | None = None) -> None:
        self._flags: dict[str, Any] = flags or {}

    def is_enabled(
        self,
        flag_key: str,
        default: bool = False,
        context: dict[str, Any] | None = None,
    ) -> bool:
        return bool(self._flags.get(flag_key, default))

    def get_string(
        self,
        flag_key: str,
        default: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        return str(self._flags.get(flag_key, default))

    def get_number(
        self,
        flag_key: str,
        default: float = 0.0,
        context: dict[str, Any] | None = None,
    ) -> float:
        return float(self._flags.get(flag_key, default))


# ── Provider factory ───────────────────────────────────────────────────────

_provider: FlagsProvider | None = None


def get_provider() -> FlagsProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_FLAGS_BACKEND", "env").lower()

    if backend in ("env", "mock"):
        _provider = EnvFlagsProvider()
    else:
        raise ConfigurationError(
            f"Unknown PLATFORM_FLAGS_BACKEND: {backend!r}. "
            "Supported: env, mock"
        )
    return _provider


# ── Public API ─────────────────────────────────────────────────────────────

def is_enabled(
    flag_key: str,
    default: bool = False,
    context: dict[str, Any] | None = None,
) -> bool:
    """Return True if the feature flag is enabled."""
    return get_provider().is_enabled(flag_key, default, context)


def get_flag(
    flag_key: str,
    default: Any = None,
    context: dict[str, Any] | None = None,
) -> Any:
    """Return a flag value (string or number). Use is_enabled for booleans."""
    p = get_provider()
    if default is None or isinstance(default, str):
        return p.get_string(flag_key, default or "", context)
    if isinstance(default, (int, float)):
        return p.get_number(flag_key, float(default), context)
    return p.is_enabled(flag_key, bool(default), context)


__all__ = [
    "FlagsProvider",
    "EnvFlagsProvider",
    "MockFlagsProvider",
    "get_provider",
    "is_enabled",
    "get_flag",
]
