"""
platform_sdk.tier1_runtime.retry
───────────────────────────────────
Standard retry/backoff/timeout policy with jitter.
Backed by Tenacity. Classifies errors as retryable or non-retryable.

Usage:
    @retry_policy()
    async def call_upstream():
        ...

    @retry_policy(max_attempts=5, on=[UpstreamError])
    async def call_stripe():
        ...
"""
from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any, Type

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

# Errors that are NEVER retried regardless of policy
_NON_RETRYABLE = (
    "platform_sdk.tier0_core.errors.AuthError",
    "platform_sdk.tier0_core.errors.ValidationError",
    "platform_sdk.tier0_core.errors.NotFoundError",
    "platform_sdk.tier0_core.errors.ForbiddenError",
)


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception should be retried."""
    fqn = f"{type(exc).__module__}.{type(exc).__qualname__}"
    if fqn in _NON_RETRYABLE:
        return False
    return True


def retry_policy(
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 10.0,
    jitter: float = 1.0,
    on: list[Type[Exception]] | None = None,
) -> Callable:
    """
    Decorator applying exponential backoff with jitter.

    Args:
        max_attempts: Total number of attempts (including first).
        min_wait:     Minimum wait seconds between retries.
        max_wait:     Maximum wait seconds between retries.
        jitter:       Maximum random seconds added to each wait.
        on:           Specific exception types to retry on. If None, retries
                      on all non-platform non-retryable errors.
    """
    def decorator(fn: Callable) -> Callable:
        import functools

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if on:
                retry_on = retry_if_exception_type(tuple(on))
            else:
                retry_on = retry_if_exception(_is_retryable)

            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(min=min_wait, max=max_wait) + wait_random(0, jitter),
                retry=retry_on,
                reraise=True,
            ):
                with attempt:
                    return await fn(*args, **kwargs)

        return wrapper
    return decorator
