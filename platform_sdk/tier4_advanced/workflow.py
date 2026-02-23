"""
platform_sdk.tier4_advanced.workflow
──────────────────────────────────────
Durable workflow primitives backed by Temporal. Provides workflow
definition, activity registration, and client stubs for orchestrating
long-running, fault-tolerant processes.

Minimal stack: DEFERRED — add when processes require durable execution
with replay, signals, or human-in-the-loop steps.
"""
from __future__ import annotations

from typing import Any, Callable


def workflow(name: str | None = None) -> Callable:
    """
    Decorator placeholder for Temporal workflow classes.
    Replace implementation with temporalio.workflow.defn when Temporal is added.
    """
    def decorator(cls: Any) -> Any:
        cls.__workflow_name__ = name or cls.__name__
        return cls
    return decorator


def activity(fn: Callable) -> Callable:
    """
    Decorator placeholder for Temporal activity functions.
    Replace implementation with temporalio.activity.defn when Temporal is added.
    """
    fn.__activity__ = True  # type: ignore[attr-defined]
    return fn


__all__ = ["workflow", "activity"]
