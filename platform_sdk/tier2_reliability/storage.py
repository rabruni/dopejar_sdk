"""
platform_sdk.tier2_reliability.storage
────────────────────────────────────────
Blob storage abstraction (S3-compatible). Provides a unified interface for
uploading, downloading, deleting, and listing objects regardless of the
underlying provider (AWS S3, Cloudflare R2, MinIO, local filesystem).

Minimal stack: DEFERRED — add when file uploads or large object storage
is required.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Protocol, runtime_checkable

from platform_sdk.tier0_core.errors import ConfigurationError


@dataclass
class StorageObject:
    key: str
    size: int
    content_type: str = "application/octet-stream"
    metadata: dict[str, str] | None = None


@runtime_checkable
class StorageProvider(Protocol):
    async def upload(
        self,
        key: str,
        data: bytes | io.IOBase,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str: ...  # returns public or signed URL

    async def download(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def list(self, prefix: str = "") -> AsyncIterator[StorageObject]: ...

    async def get_url(self, key: str, expires_in: int = 3600) -> str: ...


class LocalStorageProvider:
    """
    Filesystem-backed storage for local dev and tests.
    Stores objects under PLATFORM_STORAGE_LOCAL_PATH (default: /tmp/platform_storage).
    """

    def __init__(self, base_path: str | None = None) -> None:
        self._base = Path(
            base_path or os.environ.get("PLATFORM_STORAGE_LOCAL_PATH", "/tmp/platform_storage")
        )
        self._base.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        key: str,
        data: bytes | io.IOBase,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = data if isinstance(data, bytes) else data.read()
        path.write_bytes(raw)
        return f"file://{path}"

    async def download(self, key: str) -> bytes:
        path = self._base / key
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key!r}")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._base / key
        if path.exists():
            path.unlink()

    async def list(self, prefix: str = "") -> AsyncIterator[StorageObject]:
        for p in sorted(self._base.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(self._base))
            if prefix and not rel.startswith(prefix):
                continue
            yield StorageObject(key=rel, size=p.stat().st_size)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        return f"file://{self._base / key}"


MockStorageProvider = LocalStorageProvider  # alias for tests


_provider: StorageProvider | None = None


def get_provider() -> StorageProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_STORAGE_BACKEND", "local").lower()
    if backend in ("local", "mock"):
        _provider = LocalStorageProvider()
    else:
        raise ConfigurationError(
            f"Unknown PLATFORM_STORAGE_BACKEND: {backend!r}. Supported: local, mock"
        )
    return _provider


async def upload(key: str, data: bytes | io.IOBase, **kwargs: str) -> str:
    return await get_provider().upload(key, data, **kwargs)


async def download(key: str) -> bytes:
    return await get_provider().download(key)


async def delete(key: str) -> None:
    await get_provider().delete(key)


async def get_url(key: str, expires_in: int = 3600) -> str:
    return await get_provider().get_url(key, expires_in)


__all__ = [
    "StorageObject", "StorageProvider", "LocalStorageProvider",
    "MockStorageProvider", "get_provider", "upload", "download", "delete", "get_url",
]
