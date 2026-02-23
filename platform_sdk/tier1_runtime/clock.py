"""
platform_sdk.tier1_runtime.clock
──────────────────────────────────
Mockable time source. All application code that needs the current time should
call platform_sdk functions here instead of datetime.now() or time.time()
directly. This makes time fully controllable in tests (no more freezegun as
a hard dependency).

Minimal stack: DEFERRED — add when deterministic time in tests is required.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable


# ── Clock implementation ───────────────────────────────────────────────────

class Clock:
    """Mockable clock. Override _now_fn to control time in tests."""

    def __init__(self, now_fn: Callable[[], datetime] | None = None) -> None:
        self._now_fn = now_fn or (lambda: datetime.now(tz=timezone.utc))

    def now(self) -> datetime:
        """Return the current UTC datetime."""
        return self._now_fn()

    def timestamp(self) -> float:
        """Return the current Unix timestamp (float seconds)."""
        return self.now().timestamp()

    def timestamp_ms(self) -> int:
        """Return the current Unix timestamp in milliseconds."""
        return int(self.timestamp() * 1000)

    def freeze(self, dt: datetime) -> "Clock":
        """Return a new Clock frozen at the given datetime."""
        return Clock(now_fn=lambda: dt)

    def advance(self, seconds: float) -> "Clock":
        """Return a new Clock advanced by *seconds* from current time."""
        base = self.now()
        return Clock(now_fn=lambda: datetime.fromtimestamp(
            base.timestamp() + seconds, tz=timezone.utc
        ))


# ── Module-level singleton ─────────────────────────────────────────────────

_clock = Clock()


def get_clock() -> Clock:
    """Return the global clock instance."""
    return _clock


def set_clock(clock: Clock) -> None:
    """Replace the global clock (use in tests)."""
    global _clock
    _clock = clock


def now() -> datetime:
    """Return the current UTC datetime."""
    return _clock.now()


def timestamp() -> float:
    """Return the current Unix timestamp."""
    return _clock.timestamp()


def timestamp_ms() -> int:
    """Return the current Unix timestamp in milliseconds."""
    return _clock.timestamp_ms()


__all__ = ["Clock", "get_clock", "set_clock", "now", "timestamp", "timestamp_ms"]
