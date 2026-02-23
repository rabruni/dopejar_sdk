"""
platform_sdk.tier0_core.secrets
─────────────────────────────────
Secret retrieval, rotation hooks, least-privilege access.
Secrets are wrapped in SecretStr — they cannot be logged or serialized.

Minimal stack: env vars (dev) | Infisical (prod) | OpenBao (self-hosted)
Select via:    PLATFORM_SECRETS_BACKEND=env|infisical|vault|mock
"""
from __future__ import annotations

import os
from typing import Callable, Protocol, runtime_checkable


# ── SecretStr — prevents logging/serialization ────────────────────────────────

class SecretStr:
    """
    Wrapper that hides the secret value from logs, repr, and JSON.
    Access the raw value only via .get_secret_value().
    """

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretStr('**********')"

    def __str__(self) -> str:
        return "**********"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretStr):
            return self._value == other._value
        return False


# ── Provider protocol ─────────────────────────────────────────────────────────

@runtime_checkable
class SecretsProvider(Protocol):
    def get(self, key: str) -> SecretStr: ...
    def set(self, key: str, value: str) -> None: ...


# ── Rotation registry ─────────────────────────────────────────────────────────

_rotation_hooks: dict[str, list[Callable[[str], None]]] = {}


def on_rotation(key: str) -> Callable:
    """
    Register a callback that fires when a secret is rotated.

    Usage:
        @on_rotation("stripe_api_key")
        def _update_stripe(new_value: str):
            stripe.api_key = new_value
    """
    def decorator(fn: Callable[[str], None]) -> Callable:
        _rotation_hooks.setdefault(key, []).append(fn)
        return fn
    return decorator


def _fire_rotation(key: str, new_value: str) -> None:
    for hook in _rotation_hooks.get(key, []):
        hook(new_value)


# ── Env provider (dev / simple deployments) ────────────────────────────────────

class EnvSecretsProvider:
    """Reads secrets from environment variables. Suitable for local dev."""

    def get(self, key: str) -> SecretStr:
        value = os.environ.get(key.upper())
        if value is None:
            from platform_sdk.tier0_core.errors import ConfigurationError
            raise ConfigurationError(
                "secret_not_found",
                f"Secret {key!r} not found in environment.",
            )
        return SecretStr(value)

    def set(self, key: str, value: str) -> None:
        os.environ[key.upper()] = value


# ── Mock provider (tests) ─────────────────────────────────────────────────────

class MockSecretsProvider:
    """In-memory secrets store for tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> SecretStr:
        if key not in self._store:
            return SecretStr(f"mock-secret-for-{key}")
        return SecretStr(self._store[key])

    def set(self, key: str, value: str) -> None:
        self._store[key] = value


# ── Infisical provider ────────────────────────────────────────────────────────

class InfisicalProvider:
    """
    Infisical secrets backend.
    Requires: INFISICAL_TOKEN, INFISICAL_PROJECT_ID
    Optional: INFISICAL_ENVIRONMENT (default: "prod"), INFISICAL_SITE_URL
    """

    def __init__(self) -> None:
        try:
            from infisical_sdk import InfisicalSDKClient
        except ImportError as e:
            raise ImportError(
                "Install infisical-python: pip install infisical-sdk"
            ) from e

        token = os.environ["INFISICAL_TOKEN"]
        site_url = os.getenv("INFISICAL_SITE_URL", "https://app.infisical.com")
        self._project_id = os.environ["INFISICAL_PROJECT_ID"]
        self._env = os.getenv("INFISICAL_ENVIRONMENT", "prod")
        self._client = InfisicalSDKClient(host=site_url, auth={"token": token})

    def get(self, key: str) -> SecretStr:
        secret = self._client.getSecret(
            secret_name=key,
            project_id=self._project_id,
            environment_slug=self._env,
        )
        return SecretStr(secret.secretValue)

    def set(self, key: str, value: str) -> None:
        raise NotImplementedError("Use the Infisical dashboard to set secrets.")


# ── Provider registry ─────────────────────────────────────────────────────────

_provider: SecretsProvider | None = None


def _build_provider() -> SecretsProvider:
    name = os.getenv("PLATFORM_SECRETS_BACKEND", "env").lower()
    if name in ("env", "none"):
        return EnvSecretsProvider()
    if name == "mock":
        return MockSecretsProvider()
    if name == "infisical":
        return InfisicalProvider()
    raise EnvironmentError(
        f"Unknown PLATFORM_SECRETS_BACKEND={name!r}. "
        "Valid: env, mock, infisical"
    )


def get_provider() -> SecretsProvider:
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _reset_provider() -> None:
    global _provider
    _provider = None


# ── Public API ────────────────────────────────────────────────────────────────

def get_secret(key: str) -> SecretStr:
    """Retrieve a secret by name. Returns SecretStr — value is never logged."""
    return get_provider().get(key)
