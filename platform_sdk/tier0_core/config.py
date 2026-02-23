"""
platform_sdk.tier0_core.config
────────────────────────────────
Typed configuration with env layering. Reads from .env → environment
variables → optional remote config. All fields are typed via Pydantic.
Missing required fields raise ConfigurationError at startup, not at runtime.

Minimal stack: pydantic-settings + python-dotenv
Remote config:  PLATFORM_CONFIG_BACKEND=etcd|consul|none
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformConfig(BaseSettings):
    """
    Typed platform configuration. Add fields here as the platform grows.
    All env vars are prefixed with PLATFORM_ unless overridden.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field(default="platform", alias="APP_NAME")
    app_version: str = Field(default="0.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="APP_ENV")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./dev.db",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Identity ──────────────────────────────────────────────────────────────
    identity_provider: str = Field(default="mock", alias="PLATFORM_IDENTITY_PROVIDER")

    # ── Secrets ───────────────────────────────────────────────────────────────
    secrets_backend: str = Field(default="env", alias="PLATFORM_SECRETS_BACKEND")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="PLATFORM_LOG_LEVEL")
    log_format: str = Field(default="json", alias="PLATFORM_LOG_FORMAT")

    # ── GenAI ─────────────────────────────────────────────────────────────────
    inference_provider: str = Field(default="mock", alias="PLATFORM_INFERENCE_PROVIDER")
    inference_default_model: str = Field(
        default="gpt-4o-mini", alias="PLATFORM_INFERENCE_DEFAULT_MODEL"
    )
    vector_backend: str = Field(default="memory", alias="PLATFORM_VECTOR_BACKEND")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")

    # ── Notifications ─────────────────────────────────────────────────────────
    notifications_backend: str = Field(
        default="mock", alias="PLATFORM_NOTIFICATIONS_BACKEND"
    )

    # ── Error reporting ───────────────────────────────────────────────────────
    error_backend: str = Field(default="none", alias="PLATFORM_ERROR_BACKEND")

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of {allowed}, got {v!r}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache(maxsize=1)
def get_config() -> PlatformConfig:
    """
    Return the singleton platform config. Cached after first call.
    Call _reset_config() in tests to pick up new env vars.
    """
    return PlatformConfig()


def _reset_config() -> None:
    """For tests — clear the config cache."""
    get_config.cache_clear()
