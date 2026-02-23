"""
platform_sdk.tier3_platform.policy
─────────────────────────────────────
Policy-as-code via OPA (Open Policy Agent) integration. Decouples business
rules from application code — policies live in .rego files and are evaluated
at runtime without redeploy.

Backed by: OPA HTTP API, embedded rego (py-opa), or rule-based mock.

Minimal stack: DEFERRED — add when compliance or complex authorization
policies exceed what simple RBAC can express.
"""
from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PolicyProvider(Protocol):
    async def evaluate(
        self,
        policy_path: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def allows(
        self,
        policy_path: str,
        input_data: dict[str, Any],
    ) -> bool: ...


class MockPolicyProvider:
    """Always-allow mock provider for tests."""

    def __init__(self, default_allow: bool = True) -> None:
        self._default_allow = default_allow
        self._overrides: dict[str, bool] = {}

    def set_policy(self, policy_path: str, allow: bool) -> None:
        self._overrides[policy_path] = allow

    async def evaluate(
        self, policy_path: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        allow = self._overrides.get(policy_path, self._default_allow)
        return {"result": {"allow": allow}}

    async def allows(self, policy_path: str, input_data: dict[str, Any]) -> bool:
        result = await self.evaluate(policy_path, input_data)
        return bool(result.get("result", {}).get("allow", False))


_provider: PolicyProvider | None = None


def get_provider() -> PolicyProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_POLICY_BACKEND", "mock").lower()
    if backend == "mock":
        _provider = MockPolicyProvider()
    else:
        raise ValueError(f"Unknown PLATFORM_POLICY_BACKEND: {backend!r}. Supported: mock")
    return _provider


async def evaluate(policy_path: str, input_data: dict[str, Any]) -> dict[str, Any]:
    return await get_provider().evaluate(policy_path, input_data)


async def allows(policy_path: str, input_data: dict[str, Any]) -> bool:
    return await get_provider().allows(policy_path, input_data)


__all__ = ["PolicyProvider", "MockPolicyProvider", "get_provider", "evaluate", "allows"]
