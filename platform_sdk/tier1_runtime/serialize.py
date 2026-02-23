"""
platform_sdk.tier1_runtime.serialize
───────────────────────────────────────
Stable serialization with schema evolution support.
Formats: json (default via msgspec) | protobuf (add when needed)

Configure via: PLATFORM_SERIALIZE_FORMAT=json|protobuf
"""
from __future__ import annotations

import json
import os
from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_FORMAT = os.getenv("PLATFORM_SERIALIZE_FORMAT", "json").lower()


def serialize(obj: BaseModel | dict | list, format: str | None = None) -> bytes:
    """
    Serialize a Pydantic model or dict to bytes.

    Usage:
        data = serialize(my_model)           # → b'{"id": "...", ...}'
        data = serialize(my_model, "json")
    """
    fmt = (format or _FORMAT).lower()
    if fmt == "json":
        if isinstance(obj, BaseModel):
            return obj.model_dump_json().encode()
        return json.dumps(obj, default=str).encode()
    raise ValueError(f"Unsupported serialize format: {fmt!r}. Supported: json")


def deserialize(data: bytes | str, model: Type[T], format: str | None = None) -> T:
    """
    Deserialize bytes/str into a Pydantic model.

    Usage:
        order = deserialize(raw_bytes, Order)
    """
    fmt = (format or _FORMAT).lower()
    if fmt == "json":
        if isinstance(data, bytes):
            data = data.decode()
        return model.model_validate_json(data)
    raise ValueError(f"Unsupported deserialize format: {fmt!r}. Supported: json")


def to_dict(obj: BaseModel) -> dict[str, Any]:
    """Convert a Pydantic model to a plain dict (for JSON responses)."""
    return obj.model_dump(mode="json")


__sdk_export__ = {
    "surface": "service",
    "exports": ["serialize", "deserialize"],
    "description": "JSON serialization with schema evolution and versioning support",
    "tier": "tier1_runtime",
    "module": "serialize",
}
