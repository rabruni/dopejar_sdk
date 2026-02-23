"""
platform_sdk.tier3_platform.authorization
────────────────────────────────────────────
Fine-grained resource-level permissions — who can do X on resource Y.
Relationship-based access control (Google Zanzibar model).

Minimal stack: simple in-memory RBAC (dev) | SpiceDB (prod)
Configure via: PLATFORM_AUTHZ_BACKEND=simple|spicedb|mock
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from platform_sdk.tier0_core.identity import Principal


# ── Protocol ──────────────────────────────────────────────────────────────────

@runtime_checkable
class AuthzProvider(Protocol):
    async def can(
        self, principal: Principal, action: str, resource: str
    ) -> bool: ...

    async def grant(
        self, principal_id: str, action: str, resource: str
    ) -> None: ...

    async def revoke(
        self, principal_id: str, action: str, resource: str
    ) -> None: ...


# ── Simple in-process RBAC (dev/test) ─────────────────────────────────────────

class SimpleAuthzProvider:
    """
    In-memory RBAC. Grants stored as (principal_id, action, resource) tuples.
    Role-based: principals with role "admin" can do anything.
    """

    def __init__(self) -> None:
        self._grants: set[tuple[str, str, str]] = set()
        # Wildcard resource grants: (principal_id, action, "*")
        self._role_policies: dict[str, set[str]] = {
            "admin": {"*"},
            "user":  {"read"},
        }

    async def can(self, principal: Principal, action: str, resource: str) -> bool:
        # Admin role can do anything
        if "admin" in principal.roles:
            return True

        # Check role-based policies
        for role in principal.roles:
            allowed_actions = self._role_policies.get(role, set())
            if "*" in allowed_actions or action in allowed_actions:
                return True

        # Check explicit grants
        if (principal.id, action, resource) in self._grants:
            return True
        if (principal.id, action, "*") in self._grants:
            return True

        return False

    async def grant(self, principal_id: str, action: str, resource: str) -> None:
        self._grants.add((principal_id, action, resource))

    async def revoke(self, principal_id: str, action: str, resource: str) -> None:
        self._grants.discard((principal_id, action, resource))


# ── SpiceDB provider ──────────────────────────────────────────────────────────

class SpiceDBProvider:
    """
    SpiceDB (Google Zanzibar model) provider.
    Requires: SPICEDB_ENDPOINT, SPICEDB_API_KEY
    """

    def __init__(self) -> None:
        try:
            import authzed.api.v1 as authzed
            from authzed.api.v1 import Client, SyncClient
            from grpcutil import bearer_token_credentials
        except ImportError as e:
            raise ImportError(
                "Install authzed: pip install authzed"
            ) from e

        endpoint = os.environ["SPICEDB_ENDPOINT"]
        api_key = os.environ["SPICEDB_API_KEY"]
        self._client = SyncClient(endpoint, bearer_token_credentials(api_key))
        self._schema_prefix = os.getenv("SPICEDB_SCHEMA_PREFIX", "platform")

    async def can(self, principal: Principal, action: str, resource: str) -> bool:
        import authzed.api.v1 as authzed

        resource_type, resource_id = resource.split(":", 1) if ":" in resource else ("resource", resource)

        resp = self._client.CheckPermission(
            authzed.CheckPermissionRequest(
                resource=authzed.ObjectReference(
                    object_type=f"{self._schema_prefix}/{resource_type}",
                    object_id=resource_id,
                ),
                permission=action,
                subject=authzed.SubjectReference(
                    object=authzed.ObjectReference(
                        object_type=f"{self._schema_prefix}/user",
                        object_id=principal.id,
                    )
                ),
            )
        )
        return resp.permissionship == authzed.CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION

    async def grant(self, principal_id: str, action: str, resource: str) -> None:
        raise NotImplementedError("Use SpiceDB schema to manage relationships.")

    async def revoke(self, principal_id: str, action: str, resource: str) -> None:
        raise NotImplementedError("Use SpiceDB schema to manage relationships.")


# ── Provider registry ─────────────────────────────────────────────────────────

_provider: AuthzProvider | None = None


def _build_provider() -> AuthzProvider:
    name = os.getenv("PLATFORM_AUTHZ_BACKEND", "simple").lower()
    if name in ("simple", "mock"):
        return SimpleAuthzProvider()
    if name == "spicedb":
        return SpiceDBProvider()
    raise EnvironmentError(f"Unknown PLATFORM_AUTHZ_BACKEND={name!r}. Valid: simple, spicedb")


def get_provider() -> AuthzProvider:
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _reset_provider() -> None:
    global _provider
    _provider = None


# ── Public API ────────────────────────────────────────────────────────────────

async def can(principal: Principal, action: str, resource: str) -> bool:
    """
    Check if a principal can perform an action on a resource.

    Args:
        principal: The authenticated principal (from identity.verify_token).
        action:    The action string, e.g. "order:cancel", "user:read".
        resource:  The resource identifier, e.g. "order:ord_123", "user:u_456".

    Returns:
        True if allowed, False if denied.
    """
    return await get_provider().can(principal, action, resource)


async def require_permission(
    principal: Principal, action: str, resource: str
) -> None:
    """
    Assert that a principal can perform an action. Raises ForbiddenError if not.

    Usage:
        await require_permission(principal, "order:cancel", f"order:{order_id}")
    """
    if not await can(principal, action, resource):
        from platform_sdk.tier0_core.errors import ForbiddenError
        raise ForbiddenError(
            "forbidden",
            f"Permission denied: {action} on {resource}",
        )
