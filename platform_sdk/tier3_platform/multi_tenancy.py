"""
platform_sdk.tier3_platform.multi_tenancy
───────────────────────────────────────────
Tenant isolation utilities. Ensures that data, resources, and operations
are always scoped to the correct tenant (org_id). Prevents cross-tenant
data leakage by providing query filters, context validation, and per-tenant
configuration.

Minimal stack: DEFERRED — add when the platform serves multiple customers
with isolation requirements.
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TenantContext:
    org_id: str
    plan: str = "free"  # free | pro | enterprise
    features: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


_tenant_context: ContextVar[TenantContext | None] = ContextVar(
    "tenant_context", default=None
)


def set_tenant(tenant: TenantContext) -> None:
    """Set the current tenant context (call at request boundary)."""
    _tenant_context.set(tenant)


def get_tenant() -> TenantContext | None:
    """Return the current tenant context, or None if not set."""
    return _tenant_context.get()


def require_tenant() -> TenantContext:
    """Return the current tenant context, raising if not set."""
    ctx = _tenant_context.get()
    if ctx is None:
        raise RuntimeError(
            "No tenant context set. Call set_tenant() at the request boundary."
        )
    return ctx


def tenant_filter(org_id: str | None = None) -> dict[str, str]:
    """
    Return a dict suitable for filtering queries to the current tenant.
    Pass *org_id* to override; otherwise uses the current context.

    Usage (SQLAlchemy)::

        users = session.query(User).filter_by(**tenant_filter()).all()
    """
    if org_id is None:
        ctx = require_tenant()
        org_id = ctx.org_id
    return {"org_id": org_id}


def has_feature(feature: str) -> bool:
    """Check if the current tenant has a specific feature flag enabled."""
    ctx = get_tenant()
    if ctx is None:
        return False
    return feature in ctx.features


__all__ = [
    "TenantContext", "set_tenant", "get_tenant", "require_tenant",
    "tenant_filter", "has_feature",
]
