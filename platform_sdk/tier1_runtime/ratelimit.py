"""
platform_sdk.tier1_runtime.ratelimit
───────────────────────────────────────
Token bucket rate limiting — local (in-process) or distributed (Redis).
Raises RateLimitError with retry_after when limit is exceeded.

Configure via: REDIS_URL (if using distributed limiting)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int | None = None   # seconds until quota resets


# ── In-process token bucket ───────────────────────────────────────────────────

class _InProcessBucket:
    def __init__(self, limit: int, window: int) -> None:
        self._limit = limit
        self._window = window
        self._counts: dict[str, tuple[int, float]] = {}  # key → (count, window_start)

    def check(self, key: str) -> RateLimitResult:
        now = time.monotonic()
        count, window_start = self._counts.get(key, (0, now))

        if now - window_start >= self._window:
            count = 0
            window_start = now

        if count >= self._limit:
            retry_after = int(self._window - (now - window_start)) + 1
            return RateLimitResult(allowed=False, remaining=0, retry_after=retry_after)

        self._counts[key] = (count + 1, window_start)
        return RateLimitResult(allowed=True, remaining=self._limit - count - 1)


_buckets: dict[str, _InProcessBucket] = {}


def _get_bucket(limit: int, window: int, key_prefix: str) -> _InProcessBucket:
    bkey = f"{key_prefix}:{limit}:{window}"
    if bkey not in _buckets:
        _buckets[bkey] = _InProcessBucket(limit, window)
    return _buckets[bkey]


# ── Public API ────────────────────────────────────────────────────────────────

def check_rate_limit(
    key: str,
    limit: int = 100,
    window: int = 60,
) -> RateLimitResult:
    """
    Check and increment rate limit for the given key.
    Raises RateLimitError if limit exceeded.

    Args:
        key:    Unique key, e.g. "ip:1.2.3.4", "user:u_123", "org:o_456"
        limit:  Max requests per window.
        window: Window duration in seconds.

    Usage:
        check_rate_limit(f"user:{user_id}", limit=60, window=60)
    """
    redis_url = os.getenv("REDIS_URL")

    if redis_url:
        result = _redis_check(key, limit, window, redis_url)
    else:
        bucket = _get_bucket(limit, window, "local")
        result = bucket.check(key)

    if not result.allowed:
        from platform_sdk.tier0_core.errors import RateLimitError
        raise RateLimitError(
            retry_after=result.retry_after,
            user_message=f"Rate limit exceeded. Try again in {result.retry_after}s.",
        )

    return result


def _redis_check(key: str, limit: int, window: int, redis_url: str) -> RateLimitResult:
    """Distributed token bucket via Redis INCR + EXPIRE."""
    try:
        import redis

        r = redis.from_url(redis_url, decode_responses=True)
        redis_key = f"ratelimit:{key}"

        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.ttl(redis_key)
        count, ttl = pipe.execute()

        if ttl == -1:
            r.expire(redis_key, window)
            ttl = window

        if count > limit:
            return RateLimitResult(allowed=False, remaining=0, retry_after=max(ttl, 1))

        return RateLimitResult(allowed=True, remaining=limit - count)
    except Exception:
        # Redis unavailable — fall back to in-process
        bucket = _get_bucket(limit, window, "fallback")
        return bucket.check(key)


# ── MCP handler ───────────────────────────────────────────────────────────────

async def _mcp_check_rate_limit(args: dict) -> dict:
    from platform_sdk.tier0_core.errors import RateLimitError
    try:
        result = check_rate_limit(
            key=args["key"],
            limit=args["limit"],
            window=args.get("window_seconds", 60),
        )
        return {"key": args["key"], "allowed": result.allowed, "remaining": result.remaining}
    except RateLimitError as exc:
        return {
            "key": args["key"],
            "allowed": False,
            "remaining": 0,
            "retry_after": exc.retry_after,
        }


__sdk_export__ = {
    "surface": "service",
    "exports": ["check_rate_limit"],
    "mcp_tools": [
        {
            "name": "check_rate_limit",
            "description": "Check if a key is within rate limit. Returns allowed=true/false.",
            "schema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "description": "Max requests per window",
                    },
                    "window_seconds": {"type": "integer", "default": 60},
                },
                "required": ["key", "limit"],
            },
            "handler": "_mcp_check_rate_limit",
        },
    ],
    "description": "Token-bucket rate limiting (in-process or Redis-distributed)",
    "tier": "tier1_runtime",
    "module": "ratelimit",
}
