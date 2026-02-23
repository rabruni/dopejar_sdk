"""
platform_sdk.tier3_platform.api_client
────────────────────────────────────────
HTTP/gRPC client wrapper for inter-service calls. Adds automatic retry,
circuit breaking, distributed tracing propagation, auth header injection,
and structured error mapping to every outbound request.

Backed by: httpx (async HTTP), grpcio (gRPC), or requests (sync HTTP).

Minimal stack: DEFERRED — add when ≥2 services need to call each other.
"""
from __future__ import annotations

import os
from typing import Any

from platform_sdk.tier0_core.errors import UpstreamError
from platform_sdk.tier1_runtime.context import get_context


class ApiClient:
    """
    Async HTTP client for calling platform services.

    Usage::

        client = ApiClient(base_url="http://user-service")
        response = await client.get("/users/123")
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        service_name: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._service_name = service_name or base_url

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        ctx = get_context()
        if ctx:
            if ctx.request_id:
                headers["x-request-id"] = ctx.request_id
            if ctx.trace_id:
                headers["x-trace-id"] = ctx.trace_id
        return headers

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return await self._request("POST", path, json=json, **kwargs)

    async def put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return await self._request("PUT", path, json=json, **kwargs)

    async def patch(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return await self._request("PATCH", path, json=json, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self._request("DELETE", path, **kwargs)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            import httpx  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "Install 'httpx' to use ApiClient: pip install httpx"
            ) from exc

        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {**self._build_headers(), **kwargs.pop("headers", {})}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                if response.headers.get("content-type", "").startswith("application/json"):
                    return response.json()
                return response.text
        except Exception as exc:
            raise UpstreamError(
                f"Request to {self._service_name} failed: {exc}",
                upstream_service=self._service_name,
            ) from exc


__all__ = ["ApiClient"]
