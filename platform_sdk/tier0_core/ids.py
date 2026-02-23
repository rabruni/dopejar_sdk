"""
platform_sdk.tier0_core.ids
────────────────────────────
ID generation utilities. Provides UUID v4, UUID v7 (time-ordered), and ULID
generation. All services should use these helpers to ensure consistent ID
formats across the platform.

Minimal stack: DEFERRED — add when ID consistency across services is required.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Literal


# ── UUID helpers ───────────────────────────────────────────────────────────

def new_uuid4() -> str:
    """Generate a random UUID v4 string."""
    return str(uuid.uuid4())


def new_uuid7() -> str:
    """
    Generate a time-ordered UUID v7 string (monotonic, sortable).
    Falls back to a UUID v4 prefixed with timestamp if uuid7 is not available.
    """
    try:
        import uuid_extensions  # type: ignore[import]
        return str(uuid_extensions.uuid7())
    except ImportError:
        # Fallback: encode ms timestamp into first 48 bits of a UUID4
        ms = int(time.time() * 1000)
        rand_bits = int.from_bytes(os.urandom(10), "big")
        # Build 128-bit value: 48-bit timestamp | version(4) | 12-bit rand | variant | 62-bit rand
        uuid_int = (ms << 80) | (0x7000 << 64) | (rand_bits & 0x0FFFFFFFFFFFFFFFFFFFFFFF)
        return str(uuid.UUID(int=uuid_int))


def new_ulid() -> str:
    """
    Generate a ULID (Universally Unique Lexicographically Sortable Identifier).
    Requires `python-ulid` package. Falls back to uuid7 if unavailable.
    """
    try:
        from ulid import ULID  # type: ignore[import]
        return str(ULID())
    except ImportError:
        return new_uuid7()


def new_id(kind: Literal["uuid4", "uuid7", "ulid"] = "uuid7") -> str:
    """
    Generate a new platform ID using the specified kind.
    Default is uuid7 (time-ordered, database-friendly).
    """
    if kind == "uuid4":
        return new_uuid4()
    elif kind == "uuid7":
        return new_uuid7()
    elif kind == "ulid":
        return new_ulid()
    raise ValueError(f"Unknown ID kind: {kind!r}. Use 'uuid4', 'uuid7', or 'ulid'.")


__all__ = ["new_uuid4", "new_uuid7", "new_ulid", "new_id"]
