"""
platform_sdk.tier2_reliability.circuit
────────────────────────────────────────
Circuit breaker and bulkhead patterns. Prevents cascade failures by
temporarily stopping calls to a dependency that is failing, giving it time
to recover before traffic is resumed.

States: CLOSED (normal) → OPEN (failing, fast-fail) → HALF_OPEN (probing).

Backed by: pybreaker (OSS), or Resilience4j via sidecar (enterprise).

Minimal stack: DEFERRED — add when ≥2 external dependencies exist and
cascade failures are a documented risk.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

from platform_sdk.tier0_core.errors import UpstreamError

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5       # failures before OPEN
    recovery_timeout: float = 60.0   # seconds in OPEN before HALF_OPEN
    success_threshold: int = 2       # successes in HALF_OPEN before CLOSED
    name: str = "default"


class CircuitBreaker:
    """
    Simple circuit breaker implementation.

    Usage::

        breaker = CircuitBreaker(CircuitBreakerConfig(name="stripe"))

        @breaker.protect
        def charge_card(amount: int) -> dict: ...
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._cfg = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._cfg.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        state = self.state
        if state == CircuitState.OPEN:
            raise UpstreamError(
                f"Circuit {self._cfg.name!r} is OPEN — dependency is unavailable",
                upstream_service=self._cfg.name,
            )
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._cfg.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._cfg.failure_threshold:
            self._state = CircuitState.OPEN

    def protect(self, fn: F) -> F:
        """Decorator that wraps a function with this circuit breaker."""
        import functools

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(fn, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


__all__ = ["CircuitState", "CircuitBreakerConfig", "CircuitBreaker"]
