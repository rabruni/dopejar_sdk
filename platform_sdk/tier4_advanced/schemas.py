"""
platform_sdk.tier4_advanced.schemas
─────────────────────────────────────
Schema registry integration. Registers and validates Avro/JSON schemas for
event-driven architectures. Ensures producers and consumers share compatible
schemas, preventing silent data contract breaks.

Backed by: Karapace (OSS), Apicurio (enterprise), or in-memory mock.

Minimal stack: DEFERRED — add when event schemas need versioning and
compatibility enforcement.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class Schema:
    subject: str
    version: int
    schema_id: int
    schema_json: dict[str, Any]


class InMemorySchemaRegistry:
    """In-memory schema registry for tests and local dev."""

    def __init__(self) -> None:
        self._schemas: dict[str, list[Schema]] = {}
        self._id_counter = 1

    def register(self, subject: str, schema_json: dict[str, Any]) -> Schema:
        existing = self._schemas.setdefault(subject, [])
        version = len(existing) + 1
        schema = Schema(
            subject=subject,
            version=version,
            schema_id=self._id_counter,
            schema_json=schema_json,
        )
        self._id_counter += 1
        existing.append(schema)
        return schema

    def get_latest(self, subject: str) -> Schema | None:
        schemas = self._schemas.get(subject)
        return schemas[-1] if schemas else None

    def get_by_version(self, subject: str, version: int) -> Schema | None:
        schemas = self._schemas.get(subject, [])
        return next((s for s in schemas if s.version == version), None)


_registry: InMemorySchemaRegistry | None = None


def get_registry() -> InMemorySchemaRegistry:
    global _registry
    if _registry is None:
        _registry = InMemorySchemaRegistry()
    return _registry


__all__ = ["Schema", "InMemorySchemaRegistry", "get_registry"]
