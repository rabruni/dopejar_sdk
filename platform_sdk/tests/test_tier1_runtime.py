"""Tests for tier1_runtime modules."""
from __future__ import annotations

import pytest

from platform_sdk.tier1_runtime.clock import Clock, now, set_clock
from platform_sdk.tier1_runtime.context import RequestContext, get_context, set_context
from platform_sdk.tier1_runtime.serialize import deserialize, serialize
from platform_sdk.tier1_runtime.validate import validate_input

from datetime import datetime, timezone
from pydantic import BaseModel


# ── clock ──────────────────────────────────────────────────────────────────

class TestClock:
    def test_now_returns_utc_datetime(self):
        dt = now()
        assert dt.tzinfo is not None

    def test_frozen_clock(self):
        fixed = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = Clock().freeze(fixed)
        assert clock.now() == fixed

    def test_frozen_clock_set_global(self):
        from platform_sdk.tier1_runtime.clock import get_clock
        fixed = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        frozen = Clock().freeze(fixed)
        set_clock(frozen)
        assert now() == fixed
        # Restore
        set_clock(Clock())

    def test_timestamp_ms_is_int(self):
        from platform_sdk.tier1_runtime.clock import timestamp_ms
        ms = timestamp_ms()
        assert isinstance(ms, int)
        assert ms > 0


# ── context ────────────────────────────────────────────────────────────────

class TestContext:
    def test_set_and_get_context(self):
        ctx = RequestContext(request_id="req-abc", trace_id="trace-xyz")
        set_context(ctx)
        retrieved = get_context()
        assert retrieved is not None
        assert retrieved.request_id == "req-abc"
        assert retrieved.trace_id == "trace-xyz"

    def test_context_defaults(self):
        ctx = RequestContext()
        assert ctx.request_id is not None  # auto-generated


# ── validate ───────────────────────────────────────────────────────────────

class TestValidate:
    def test_valid_input_returns_model(self):
        class UserInput(BaseModel):
            name: str
            age: int

        result = validate_input(UserInput, {"name": "Alice", "age": 30})
        assert result.name == "Alice"
        assert result.age == 30

    def test_invalid_input_raises_validation_error(self):
        from platform_sdk.tier0_core.errors import ValidationError

        class UserInput(BaseModel):
            name: str
            age: int

        with pytest.raises(ValidationError):
            validate_input(UserInput, {"name": "Alice", "age": "not-a-number"})

    def test_missing_required_field_raises(self):
        from platform_sdk.tier0_core.errors import ValidationError

        class UserInput(BaseModel):
            name: str

        with pytest.raises(ValidationError):
            validate_input(UserInput, {})


# ── serialize ──────────────────────────────────────────────────────────────

class TestSerialize:
    def test_serialize_dict(self):
        data = {"id": "123", "name": "Alice"}
        serialized = serialize(data)
        assert isinstance(serialized, (str, bytes))

    def test_serialize_deserialize_roundtrip(self):
        class DataModel(BaseModel):
            id: str
            value: int
            active: bool

        original = DataModel(id="123", value=42, active=True)
        serialized = serialize(original)
        recovered = deserialize(serialized, DataModel)
        assert recovered.id == "123"
        assert recovered.value == 42

    def test_serialize_pydantic_model(self):
        class Item(BaseModel):
            id: str
            price: float

        item = Item(id="item-1", price=9.99)
        serialized = serialize(item)
        # serialize returns bytes
        assert b"item-1" in serialized
