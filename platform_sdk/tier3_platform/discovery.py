"""
platform_sdk.tier3_platform.discovery
───────────────────────────────────────
Service endpoint resolution. Translates logical service names to network
addresses, supporting multiple resolution strategies:
  - Static env var mapping (PLATFORM_SERVICE_<NAME>_URL)
  - Consul service catalog
  - Kubernetes DNS (svc.cluster.local)

Minimal stack: DEFERRED — add when ≥3 services exist and hardcoded URLs
become unmanageable.
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class DiscoveryProvider(Protocol):
    def resolve(self, service_name: str) -> str: ...


class EnvDiscoveryProvider:
    """
    Resolve service URLs from environment variables.
    PLATFORM_SERVICE_<SERVICE_NAME>_URL=http://...
    Falls back to http://<service_name> if not set.
    """

    def resolve(self, service_name: str) -> str:
        env_key = f"PLATFORM_SERVICE_{service_name.upper().replace('-', '_')}_URL"
        return os.environ.get(env_key, f"http://{service_name}")


class KubernetesDNSProvider:
    """
    Resolve service URLs via Kubernetes internal DNS.
    Pattern: http://<service>.<namespace>.svc.cluster.local
    """

    def __init__(self, namespace: str = "default", port: int = 80) -> None:
        self._namespace = namespace
        self._port = port

    def resolve(self, service_name: str) -> str:
        return f"http://{service_name}.{self._namespace}.svc.cluster.local:{self._port}"


_provider: DiscoveryProvider | None = None


def get_provider() -> DiscoveryProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_DISCOVERY_BACKEND", "env").lower()
    if backend == "env":
        _provider = EnvDiscoveryProvider()
    elif backend == "k8s":
        _provider = KubernetesDNSProvider(
            namespace=os.environ.get("PLATFORM_K8S_NAMESPACE", "default")
        )
    else:
        _provider = EnvDiscoveryProvider()
    return _provider


def resolve(service_name: str) -> str:
    """Return the base URL for a named service."""
    return get_provider().resolve(service_name)


__all__ = ["DiscoveryProvider", "EnvDiscoveryProvider", "KubernetesDNSProvider", "get_provider", "resolve"]
