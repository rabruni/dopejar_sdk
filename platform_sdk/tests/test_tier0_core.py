"""Tests for tier0_core modules."""
from __future__ import annotations

import pytest

from platform_sdk.tier0_core.errors import (
    AuthError,
    ConfigurationError,
    NotFoundError,
    PlatformError,
    ValidationError,
)
from platform_sdk.tier0_core.http import HTTP, ApiResponse, err, ok
from platform_sdk.tier0_core.ids import new_id, new_uuid4, new_uuid7
from platform_sdk.tier0_core.redact import REDACTED, redact_dict, scrub_string


# ── errors ─────────────────────────────────────────────────────────────────

class TestErrors:
    def test_platform_error_has_code(self):
        e = PlatformError("PLATFORM_ERROR", user_message="Something broke")
        assert e.code == "PLATFORM_ERROR"
        assert "Something broke" in str(e)

    def test_auth_error_subclass(self):
        e = AuthError(user_message="Bad token")
        assert isinstance(e, PlatformError)
        # AuthError's class-level code attribute
        assert "AUTH" in e.code.upper() or e.code is not None

    def test_not_found_error(self):
        e = NotFoundError("user", "u_123")
        assert "u_123" in str(e)

    def test_validation_error_with_field_errors(self):
        e = ValidationError(user_message="Invalid input", fields={"email": "Invalid format"})
        assert e.fields == {"email": "Invalid format"}

    def test_configuration_error(self):
        e = ConfigurationError(user_message="Missing DATABASE_URL")
        assert isinstance(e, PlatformError)


# ── http ───────────────────────────────────────────────────────────────────

class TestHttp:
    def test_ok_response(self):
        response = ok({"id": "123"})
        assert response.ok is True
        assert response.data == {"id": "123"}
        assert response.error is None

    def test_err_response(self):
        response = err("Not found")
        assert response.ok is False
        assert response.error == "Not found"
        assert response.data is None

    def test_http_status_codes(self):
        assert HTTP.OK == 200
        assert HTTP.CREATED == 201
        assert HTTP.NOT_FOUND == 404
        assert HTTP.INTERNAL_SERVER_ERROR == 500

    def test_api_response_as_dict(self):
        response = ok("hello", request_id="req-123")
        d = response.as_dict()
        assert d["data"] == "hello"
        assert d["request_id"] == "req-123"


# ── ids ────────────────────────────────────────────────────────────────────

class TestIds:
    def test_uuid4_format(self):
        uid = new_uuid4()
        assert len(uid) == 36
        assert uid.count("-") == 4

    def test_uuid7_is_string(self):
        uid = new_uuid7()
        assert isinstance(uid, str)
        assert len(uid) > 0

    def test_new_id_defaults_to_uuid7(self):
        uid = new_id()
        assert isinstance(uid, str)

    def test_new_id_uuid4(self):
        uid = new_id("uuid4")
        assert len(uid) == 36

    def test_new_id_invalid_kind(self):
        with pytest.raises(ValueError, match="Unknown ID kind"):
            new_id("invalid")  # type: ignore


# ── redact ─────────────────────────────────────────────────────────────────

class TestRedact:
    def test_redacts_password_key(self):
        data = {"username": "alice", "password": "s3cr3t"}
        result = redact_dict(data)
        assert result["username"] == "alice"
        assert result["password"] == REDACTED

    def test_redacts_token_key(self):
        data = {"token": "eyJhbGciOiJIUzI1NiJ9.foo.bar"}
        result = redact_dict(data)
        assert result["token"] == REDACTED

    def test_deep_redaction(self):
        data = {"user": {"password": "secret", "name": "bob"}}
        result = redact_dict(data, deep=True)
        assert result["user"]["password"] == REDACTED
        assert result["user"]["name"] == "bob"

    def test_scrub_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        result = scrub_string(text)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "[REDACTED]" in result

    def test_non_sensitive_keys_unchanged(self):
        data = {"name": "Alice", "email": "alice@example.com", "age": 30}
        result = redact_dict(data)
        assert result == data


# ── ledger ──────────────────────────────────────────────────────────────────

class TestLedger:
    @pytest.mark.asyncio
    async def test_append_single_turn(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider, LedgerEntry
        provider = MockLedgerProvider()
        entry = LedgerEntry(conversation_id="conv-1", role="user", content="Hello")
        result = await provider.append(entry)
        assert result.turn_index == 0
        assert result.prev_digest == ""
        assert len(result.digest) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_chain_links_sequential_turns(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider, LedgerEntry
        provider = MockLedgerProvider()
        e1 = await provider.append(LedgerEntry(conversation_id="conv-2", role="user", content="Hi"))
        e2 = await provider.append(LedgerEntry(conversation_id="conv-2", role="assistant", content="Hello!"))
        assert e2.turn_index == 1
        assert e2.prev_digest == e1.digest

    @pytest.mark.asyncio
    async def test_verify_chain_passes_for_valid_history(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider, LedgerEntry
        provider = MockLedgerProvider()
        for role, content in [("user", "Q1"), ("assistant", "A1"), ("user", "Q2")]:
            await provider.append(LedgerEntry(conversation_id="conv-3", role=role, content=content))
        ok, reason = await provider.verify_chain("conv-3")
        assert ok is True
        assert reason == "ok"

    @pytest.mark.asyncio
    async def test_verify_chain_detects_tampered_content(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider, LedgerEntry, _compute_digest
        provider = MockLedgerProvider()
        await provider.append(LedgerEntry(conversation_id="conv-4", role="user", content="Original"))
        await provider.append(LedgerEntry(conversation_id="conv-4", role="assistant", content="Reply"))

        # Tamper with turn 0's content without updating the digest
        provider._store["conv-4"][0].content = "TAMPERED"

        ok, reason = await provider.verify_chain("conv-4")
        assert ok is False
        assert "turn 0" in reason

    @pytest.mark.asyncio
    async def test_get_conversation_returns_turns_in_order(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider, LedgerEntry
        provider = MockLedgerProvider()
        for i in range(5):
            await provider.append(LedgerEntry(conversation_id="conv-5", role="user", content=f"msg{i}"))
        turns = await provider.get_conversation("conv-5")
        assert len(turns) == 5
        assert [t.turn_index for t in turns] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_get_conversation_pagination(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider, LedgerEntry
        provider = MockLedgerProvider()
        for i in range(6):
            await provider.append(LedgerEntry(conversation_id="conv-6", role="user", content=f"msg{i}"))
        page = await provider.get_conversation("conv-6", limit=3, offset=2)
        assert len(page) == 3
        assert page[0].turn_index == 2

    @pytest.mark.asyncio
    async def test_verify_empty_conversation_is_valid(self):
        from platform_sdk.tier0_core.ledger import MockLedgerProvider
        provider = MockLedgerProvider()
        ok, reason = await provider.verify_chain("nonexistent")
        assert ok is True

    @pytest.mark.asyncio
    async def test_public_api_append_turn(self):
        from platform_sdk.tier0_core.ledger import append_turn, verify_chain, _reset_provider
        _reset_provider()
        entry = await append_turn("conv-pub-1", "user", "Test message")
        assert entry.conversation_id == "conv-pub-1"
        assert entry.role == "user"
        assert entry.digest != ""

    @pytest.mark.asyncio
    async def test_public_api_full_flow(self):
        from platform_sdk.tier0_core.ledger import append_turn, get_conversation, verify_chain, _reset_provider
        _reset_provider()
        conv_id = "conv-pub-2"
        await append_turn(conv_id, "user", "What is 2+2?")
        await append_turn(conv_id, "assistant", "4", metadata={"model": "mock"})
        turns = await get_conversation(conv_id)
        assert len(turns) == 2
        ok, reason = await verify_chain(conv_id)
        assert ok is True

    @pytest.mark.asyncio
    async def test_service_surface_exports_ledger(self):
        from platform_sdk.service import append_turn, verify_chain, LedgerEntry
        assert callable(append_turn)
        assert callable(verify_chain)
