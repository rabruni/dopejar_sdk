"""
platform_sdk.tier0_core.identity
─────────────────────────────────
Authenticate and verify identity; normalize principals; token/session
validation; provider abstraction; multi-tenancy org model.

Minimal stack: Zitadel (OSS) | Auth0 (SaaS) | mock (tests)
Select via:    PLATFORM_IDENTITY_PROVIDER=zitadel|auth0|mock
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ── Domain model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Principal:
    """Normalized identity — provider-agnostic."""
    id: str
    email: str | None = None
    org_id: str | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def is_member_of(self, org_id: str) -> bool:
        return self.org_id == org_id


# ── Provider protocol ─────────────────────────────────────────────────────────

@runtime_checkable
class IdentityProvider(Protocol):
    """Implement this protocol to add a new identity backend."""

    def verify_token(self, token: str) -> Principal:
        """Verify a token and return the normalized Principal. Raises AuthError on failure."""
        ...

    def get_principal(self, principal_id: str) -> Principal:
        """Retrieve a principal by ID."""
        ...


# ── Mock provider (tests / local dev) ─────────────────────────────────────────

class MockIdentityProvider:
    """Deterministic mock — safe for unit tests, never calls external services."""

    def verify_token(self, token: str) -> Principal:
        if token == "invalid":
            from platform_sdk.tier0_core.errors import AuthError
            raise AuthError("invalid_token", "Token is invalid or expired")
        return Principal(
            id="mock-user-id",
            email="mock@example.com",
            org_id="mock-org-id",
            roles=("user",),
        )

    def get_principal(self, principal_id: str) -> Principal:
        return Principal(
            id=principal_id,
            email=f"{principal_id}@example.com",
            org_id="mock-org-id",
            roles=("user",),
        )


# ── Zitadel provider ──────────────────────────────────────────────────────────

class ZitadelProvider:
    """
    Zitadel JWT introspection provider.
    Requires: ZITADEL_DOMAIN, ZITADEL_INTROSPECTION_URL, ZITADEL_CLIENT_ID
    """

    def __init__(self) -> None:
        import httpx
        self._domain = os.environ["ZITADEL_DOMAIN"]
        self._introspect_url = os.getenv(
            "ZITADEL_INTROSPECTION_URL",
            f"https://{self._domain}/oauth/v2/introspect",
        )
        self._client_id = os.environ["ZITADEL_CLIENT_ID"]
        self._client_secret = os.environ.get("ZITADEL_CLIENT_SECRET", "")
        self._http = httpx.Client(timeout=5.0)

    def verify_token(self, token: str) -> Principal:
        from platform_sdk.tier0_core.errors import AuthError

        # Strip Bearer prefix if present
        if token.lower().startswith("bearer "):
            token = token[7:]

        resp = self._http.post(
            self._introspect_url,
            data={"token": token},
            auth=(self._client_id, self._client_secret),
        )
        if resp.status_code != 200:
            raise AuthError("introspection_failed", "Token introspection failed")

        data = resp.json()
        if not data.get("active"):
            raise AuthError("invalid_token", "Token is inactive or expired")

        return Principal(
            id=data.get("sub", ""),
            email=data.get("email"),
            org_id=data.get("urn:zitadel:iam:org:id") or data.get("org_id"),
            roles=tuple(data.get("roles", [])),
            metadata=data,
        )

    def get_principal(self, principal_id: str) -> Principal:
        # Zitadel Management API call — simplified
        return Principal(id=principal_id)


# ── Auth0 provider ────────────────────────────────────────────────────────────

class Auth0Provider:
    """
    Auth0 JWT verification provider.
    Requires: AUTH0_DOMAIN, AUTH0_AUDIENCE
    """

    def __init__(self) -> None:
        self._domain = os.environ["AUTH0_DOMAIN"]
        self._audience = os.environ["AUTH0_AUDIENCE"]
        self._jwks_url = f"https://{self._domain}/.well-known/jwks.json"

    def verify_token(self, token: str) -> Principal:
        import jwt as pyjwt
        from jwt.algorithms import RSAAlgorithm
        import httpx
        from platform_sdk.tier0_core.errors import AuthError

        if token.lower().startswith("bearer "):
            token = token[7:]

        try:
            resp = httpx.get(self._jwks_url, timeout=5.0)
            jwks = resp.json()
            public_key = RSAAlgorithm.from_jwk(jwks["keys"][0])
            payload = pyjwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self._audience,
            )
        except Exception as exc:
            raise AuthError("invalid_token", str(exc)) from exc

        return Principal(
            id=payload.get("sub", ""),
            email=payload.get("email"),
            org_id=payload.get("org_id"),
            roles=tuple(payload.get("permissions", [])),
            metadata=payload,
        )

    def get_principal(self, principal_id: str) -> Principal:
        return Principal(id=principal_id)


# ── Provider registry ─────────────────────────────────────────────────────────

_provider: IdentityProvider | None = None


def _build_provider() -> IdentityProvider:
    name = os.getenv("PLATFORM_IDENTITY_PROVIDER", "mock").lower()
    if name == "mock":
        return MockIdentityProvider()
    if name == "zitadel":
        return ZitadelProvider()
    if name == "auth0":
        return Auth0Provider()
    raise EnvironmentError(
        f"Unknown PLATFORM_IDENTITY_PROVIDER={name!r}. "
        "Valid options: mock, zitadel, auth0"
    )


def get_provider() -> IdentityProvider:
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _reset_provider() -> None:
    """For tests — reset provider so env changes take effect."""
    global _provider
    _provider = None


# ── Public API ────────────────────────────────────────────────────────────────

def verify_token(token: str) -> Principal:
    """Verify a token string and return the normalized Principal."""
    return get_provider().verify_token(token)


def get_principal(principal_id: str) -> Principal:
    """Retrieve a principal by ID."""
    return get_provider().get_principal(principal_id)


__sdk_export__ = {
    "surface": "service",
    "exports": ["verify_token", "get_principal", "Principal"],
    "description": "Identity verification and principal normalization (Zitadel, Auth0, mock)",
    "tier": "tier0_core",
    "module": "identity",
}
