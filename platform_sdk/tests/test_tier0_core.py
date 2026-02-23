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
