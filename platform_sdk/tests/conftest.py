"""
platform_sdk test configuration.

All tests run with mock providers by default — no external services required.
Override by setting environment variables before running pytest.
"""
from __future__ import annotations

import os

import pytest

# ── Force mock providers for all tests ────────────────────────────────────
# These must be set before any platform_sdk modules are imported.

os.environ.setdefault("PLATFORM_IDENTITY_PROVIDER", "mock")
os.environ.setdefault("PLATFORM_SECRETS_BACKEND", "mock")
os.environ.setdefault("PLATFORM_VECTOR_BACKEND", "memory")
os.environ.setdefault("PLATFORM_INFERENCE_PROVIDER", "mock")
os.environ.setdefault("PLATFORM_LLM_OBS_BACKEND", "mock")
os.environ.setdefault("PLATFORM_AUTHZ_BACKEND", "simple")
os.environ.setdefault("PLATFORM_NOTIFICATIONS_BACKEND", "mock")
os.environ.setdefault("PLATFORM_TASKS_BACKEND", "inprocess")
os.environ.setdefault("PLATFORM_FLAGS_BACKEND", "mock")
os.environ.setdefault("PLATFORM_LEDGER_BACKEND", "mock")
os.environ.setdefault("PLATFORM_ENVIRONMENT", "test")
os.environ.setdefault("PLATFORM_SERVICE_NAME", "test-service")

# Use in-memory SQLite for data module tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_module_singletons():
    """
    Reset all cached provider singletons between tests.
    This ensures each test gets a fresh provider with no state bleed.
    """
    import platform_sdk.tier0_core.identity as _identity
    import platform_sdk.tier0_core.secrets as _secrets
    import platform_sdk.tier3_platform.vector as _vector

    orig_identity = _identity._provider
    orig_secrets = _secrets._provider
    orig_vector = _vector._provider

    yield

    _identity._provider = orig_identity
    _secrets._provider = orig_secrets
    _vector._provider = orig_vector


@pytest.fixture
def mock_identity_provider():
    """Return a fresh MockIdentityProvider."""
    from platform_sdk.tier0_core.identity import MockIdentityProvider
    return MockIdentityProvider()


@pytest.fixture
def mock_secrets_provider():
    """Return a MockSecretsProvider seeded with test secrets."""
    from platform_sdk.tier0_core.secrets import MockSecretsProvider
    return MockSecretsProvider({"TEST_SECRET": "super-secret-value"})


@pytest.fixture
def mock_inference_provider():
    """Return a MockInferenceProvider with a fixed response."""
    from platform_sdk.tier4_advanced.inference import MockInferenceProvider
    return MockInferenceProvider(response="This is a mock LLM response.")


@pytest.fixture
def mock_llm_obs_provider():
    """Return a fresh MockLLMObsProvider."""
    from platform_sdk.tier4_advanced.llm_obs import MockLLMObsProvider
    return MockLLMObsProvider()
