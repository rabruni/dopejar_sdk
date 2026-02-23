"""
platform_sdk.tier4_advanced.messaging
───────────────────────────────────────
Event streaming abstraction backed by Kafka / Redpanda. Provides producer
and consumer interfaces for reliable, ordered, at-least-once event delivery.

Minimal stack: DEFERRED — add when services need decoupled async communication
via events (e.g. user.created, order.placed).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Protocol, runtime_checkable
from datetime import datetime, timezone


@dataclass
class Event:
    topic: str
    key: str
    payload: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@runtime_checkable
class MessagingProvider(Protocol):
    async def publish(self, event: Event) -> None: ...
    async def subscribe(self, topic: str) -> AsyncIterator[Event]: ...


class InMemoryMessagingProvider:
    """In-process pub/sub for tests. NOT suitable for production."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}
        self._published: list[Event] = []

    async def publish(self, event: Event) -> None:
        self._published.append(event)
        for handler in self._subscribers.get(event.topic, []):
            await handler(event)

    async def subscribe(self, topic: str) -> AsyncIterator[Event]:
        # Yield already-published events for the topic (replay)
        for event in self._published:
            if event.topic == topic:
                yield event

    def on(self, topic: str) -> Callable:
        """Register an async handler for a topic."""
        def decorator(fn: Callable) -> Callable:
            self._subscribers.setdefault(topic, []).append(fn)
            return fn
        return decorator


MockMessagingProvider = InMemoryMessagingProvider

_provider: MessagingProvider | None = None


def get_provider() -> MessagingProvider:
    global _provider
    if _provider is not None:
        return _provider
    _provider = InMemoryMessagingProvider()
    return _provider


async def publish(topic: str, key: str, payload: dict[str, Any], **headers: str) -> None:
    event = Event(topic=topic, key=key, payload=payload, headers=dict(headers))
    await get_provider().publish(event)


__all__ = ["Event", "MessagingProvider", "InMemoryMessagingProvider", "MockMessagingProvider", "get_provider", "publish"]
