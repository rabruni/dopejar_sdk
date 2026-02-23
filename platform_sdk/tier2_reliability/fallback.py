"""
platform_sdk.tier2_reliability.fallback
─────────────────────────────────────────
Standardized fallback behavior. When a primary operation fails, the fallback
module provides consistent degraded-but-functional responses rather than
surface errors to end users.

Patterns supported:
  - Static default value
  - Cached last-known-good value
  - Secondary provider call
  - Graceful degradation with observability

Minimal stack: DEFERRED — add when graceful degradation is required for
user-facing features.
"""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from platform_sdk.tier0_core.logging import get_logger

F = TypeVar("F", bound=Callable[..., Any])

logger = get_logger()


def with_fallback(
    default: Any,
    *,
    log_errors: bool = True,
    reraise: type[Exception] | tuple[type[Exception], ...] | None = None,
) -> Callable[[F], F]:
    """
    Decorator: on any exception, return *default* instead of raising.

    Args:
        default: Value to return when the wrapped function raises.
        log_errors: Whether to log the exception (default True).
        reraise: Exception type(s) that should still be raised (not caught).

    Usage::

        @with_fallback(default=[])
        def get_recommendations(user_id: str) -> list[dict]: ...
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if reraise and isinstance(exc, reraise):
                    raise
                if log_errors:
                    logger.warning(
                        "fallback_triggered",
                        function=fn.__qualname__,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                return default

        return wrapper  # type: ignore[return-value]

    return decorator


def with_secondary(
    primary: Callable[..., Any],
    secondary: Callable[..., Any],
    *,
    log_errors: bool = True,
) -> Callable[..., Any]:
    """
    Call *primary*; on failure, call *secondary* with the same arguments.

    Usage::

        get_user = with_secondary(get_user_from_db, get_user_from_cache)
    """
    @functools.wraps(primary)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return primary(*args, **kwargs)
        except Exception as exc:
            if log_errors:
                logger.warning(
                    "primary_failed_using_secondary",
                    primary=primary.__qualname__,
                    secondary=secondary.__qualname__,
                    error=str(exc),
                )
            return secondary(*args, **kwargs)

    return wrapper


class LastKnownGoodCache:
    """
    Cache that stores the last successful return value.
    On failure of the wrapped callable, returns the last good value.
    """

    def __init__(self, fn: Callable[..., Any]) -> None:
        self._fn = fn
        self._last_good: Any = None
        self._has_value = False

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        try:
            result = self._fn(*args, **kwargs)
            self._last_good = result
            self._has_value = True
            return result
        except Exception as exc:
            if self._has_value:
                logger.warning(
                    "using_last_known_good",
                    function=self._fn.__qualname__,
                    error=str(exc),
                )
                return self._last_good
            raise


__all__ = ["with_fallback", "with_secondary", "LastKnownGoodCache"]
