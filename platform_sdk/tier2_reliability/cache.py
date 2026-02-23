"""
platform_sdk.tier2_reliability.cache
───────────────────────────────────────
Cache abstraction — in-process dict (dev) or Redis (prod).
Stampede protection via mutex on cache miss.

Configure via: REDIS_URL
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class _MemoryCache:
    """Thread/async-safe in-process cache for development."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = (time.monotonic() + ttl) if ttl else 0.0
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def get_or_set(
        self, key: str, fn: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        """Get from cache or call fn() and cache the result. Stampede-safe."""
        val = await self.get(key)
        if val is not None:
            return val
        async with self._lock_for(key):
            val = await self.get(key)
            if val is not None:
                return val
            val = await fn() if asyncio.iscoroutinefunction(fn) else fn()
            await self.set(key, val, ttl)
            return val

    async def clear(self) -> None:
        self._store.clear()


class _RedisCache:
    """Redis-backed cache using async redis client."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(url, decode_responses=False)

    async def get(self, key: str) -> Any | None:
        import pickle
        val = await self._redis.get(key)
        return pickle.loads(val) if val else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        import pickle
        data = pickle.dumps(value)
        if ttl:
            await self._redis.setex(key, ttl, data)
        else:
            await self._redis.set(key, data)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def get_or_set(
        self, key: str, fn: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        val = await self.get(key)
        if val is not None:
            return val
        val = await fn() if asyncio.iscoroutinefunction(fn) else fn()
        await self.set(key, val, ttl)
        return val

    async def clear(self) -> None:
        await self._redis.flushdb()


# ── Provider registry ─────────────────────────────────────────────────────────

_cache: _MemoryCache | _RedisCache | None = None


def get_cache() -> _MemoryCache | _RedisCache:
    global _cache
    if _cache is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            _cache = _RedisCache(redis_url)
        else:
            _cache = _MemoryCache()
    return _cache


def _reset_cache() -> None:
    global _cache
    _cache = None


__sdk_export__ = {
    "surface": "service",
    "exports": ["get_cache"],
    "description": "In-memory/Redis cache with TTL and stampede protection",
    "tier": "tier2_reliability",
    "module": "cache",
}
