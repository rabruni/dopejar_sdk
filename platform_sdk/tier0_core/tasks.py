"""
platform_sdk.tier0_core.tasks
──────────────────────────────
Background job and durable workflow primitives. Provides an abstract
TaskQueue interface backed by:
  - In-process async (dev/test)
  - Hatchet / Celery (distributed background jobs)
  - Temporal (durable workflows with retries, signals, queries)

Minimal stack: DEFERRED — add when background jobs are required (e.g.,
email delivery, async report generation, webhook fan-out).
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


# ── Data models ────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    task_id: str
    status: str  # queued | running | completed | failed
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Protocol ───────────────────────────────────────────────────────────────

@runtime_checkable
class TaskQueueProvider(Protocol):
    """Abstract task queue — swap Hatchet/Temporal without changing app code."""

    async def enqueue(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        delay_seconds: int = 0,
    ) -> TaskResult: ...

    async def get_status(self, task_id: str) -> TaskResult: ...


# ── In-process provider (dev/test) ─────────────────────────────────────────

class InProcessTaskProvider:
    """
    Runs tasks immediately in-process using asyncio.
    Register handlers with @register_handler("task_name").
    NOT suitable for production — use for tests and local dev only.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {}
        self._results: dict[str, TaskResult] = {}

    def register(
        self, task_name: str
    ) -> Callable[[Callable[[dict[str, Any]], Awaitable[Any]]], Callable[[dict[str, Any]], Awaitable[Any]]]:
        def decorator(fn: Callable[[dict[str, Any]], Awaitable[Any]]) -> Callable[[dict[str, Any]], Awaitable[Any]]:
            self._handlers[task_name] = fn
            return fn
        return decorator

    async def enqueue(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        delay_seconds: int = 0,
    ) -> TaskResult:
        import uuid
        task_id = str(uuid.uuid4())
        handler = self._handlers.get(task_name)
        if not handler:
            result = TaskResult(task_id=task_id, status="failed", error=f"No handler for {task_name!r}")
            self._results[task_id] = result
            return result

        if delay_seconds:
            await asyncio.sleep(delay_seconds)

        try:
            out = await handler(payload)
            result = TaskResult(task_id=task_id, status="completed", result=out)
        except Exception as exc:
            result = TaskResult(task_id=task_id, status="failed", error=str(exc))

        self._results[task_id] = result
        return result

    async def get_status(self, task_id: str) -> TaskResult:
        if task_id in self._results:
            return self._results[task_id]
        return TaskResult(task_id=task_id, status="unknown")


class MockTaskProvider(InProcessTaskProvider):
    """Alias for InProcessTaskProvider — semantic clarity in tests."""
    pass


# ── Provider factory ───────────────────────────────────────────────────────

_provider: TaskQueueProvider | None = None


def get_provider() -> TaskQueueProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_TASKS_BACKEND", "inprocess").lower()

    if backend in ("inprocess", "mock", "local"):
        _provider = InProcessTaskProvider()
    else:
        raise ValueError(
            f"Unknown PLATFORM_TASKS_BACKEND: {backend!r}. "
            "Supported: inprocess, mock, local"
        )
    return _provider


# ── Public API ─────────────────────────────────────────────────────────────

async def enqueue(
    task_name: str,
    payload: dict[str, Any],
    *,
    queue: str = "default",
    delay_seconds: int = 0,
) -> TaskResult:
    """Enqueue a background task and return its TaskResult."""
    return await get_provider().enqueue(
        task_name, payload, queue=queue, delay_seconds=delay_seconds
    )


async def get_status(task_id: str) -> TaskResult:
    """Retrieve the current status of a queued task."""
    return await get_provider().get_status(task_id)


__all__ = [
    "TaskResult",
    "TaskQueueProvider",
    "InProcessTaskProvider",
    "MockTaskProvider",
    "get_provider",
    "enqueue",
    "get_status",
]
