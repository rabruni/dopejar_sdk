"""
platform_sdk.tier2_reliability.crypto
───────────────────────────────────────
Safe cryptographic primitives. Wraps PyNaCl / cryptography library so
application code never calls low-level crypto directly, preventing common
mistakes (ECB mode, home-rolled key derivation, raw MD5 hashing).

Provides:
  - Symmetric encryption/decryption (Fernet / XSalsa20-Poly1305)
  - Password hashing and verification (Argon2id)
  - HMAC signing and verification

Minimal stack: DEFERRED — add when data encryption at the application layer
is required (e.g., PII fields, secure tokens).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets


# ── HMAC helpers (always available, no extra deps) ─────────────────────────

def hmac_sign(key: str | bytes, data: str | bytes, *, algorithm: str = "sha256") -> str:
    """Return a hex-encoded HMAC signature for *data* using *key*."""
    k = key.encode() if isinstance(key, str) else key
    d = data.encode() if isinstance(data, str) else data
    return hmac.new(k, d, algorithm).hexdigest()


def hmac_verify(key: str | bytes, data: str | bytes, signature: str) -> bool:
    """Verify an HMAC signature in constant time."""
    expected = hmac_sign(key, data)
    return secrets.compare_digest(expected, signature)


# ── Token helpers ──────────────────────────────────────────────────────────

def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)


def generate_hex(length: int = 32) -> str:
    """Generate a cryptographically secure hex string."""
    return secrets.token_hex(length)


# ── Symmetric encryption (requires cryptography package) ──────────────────

def _get_fernet(key: str | bytes | None = None):  # type: ignore[return]
    """Return a Fernet instance, deriving a key from PLATFORM_CRYPTO_KEY if not provided."""
    try:
        from cryptography.fernet import Fernet  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "Install 'cryptography' to use symmetric encryption: pip install cryptography"
        ) from exc

    if key is None:
        raw = os.environ.get("PLATFORM_CRYPTO_KEY", "")
        if not raw:
            raise EnvironmentError(
                "PLATFORM_CRYPTO_KEY must be set for symmetric encryption. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        key = raw.encode() if isinstance(raw, str) else raw

    return Fernet(key)


def encrypt(plaintext: str | bytes, key: str | bytes | None = None) -> str:
    """Encrypt *plaintext* and return a base64 ciphertext string."""
    f = _get_fernet(key)
    data = plaintext.encode() if isinstance(plaintext, str) else plaintext
    return f.encrypt(data).decode()


def decrypt(ciphertext: str | bytes, key: str | bytes | None = None) -> bytes:
    """Decrypt a ciphertext produced by encrypt()."""
    f = _get_fernet(key)
    data = ciphertext.encode() if isinstance(ciphertext, str) else ciphertext
    return f.decrypt(data)


# ── Password hashing (requires argon2-cffi) ────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using Argon2id. Returns an encoded hash string."""
    try:
        from argon2 import PasswordHasher  # type: ignore[import]
        ph = PasswordHasher()
        return ph.hash(password)
    except ImportError:
        # Fallback to PBKDF2 if argon2-cffi is not installed
        salt = secrets.token_bytes(32)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
        return "pbkdf2$" + base64.b64encode(salt + dk).decode()


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password against a hash produced by hash_password()."""
    if encoded_hash.startswith("pbkdf2$"):
        raw = base64.b64decode(encoded_hash[7:])
        salt, dk = raw[:32], raw[32:]
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
        return secrets.compare_digest(check, dk)
    try:
        from argon2 import PasswordHasher  # type: ignore[import]
        from argon2.exceptions import VerifyMismatchError  # type: ignore[import]
        ph = PasswordHasher()
        try:
            return ph.verify(encoded_hash, password)
        except VerifyMismatchError:
            return False
    except ImportError:
        return False


__all__ = [
    "hmac_sign", "hmac_verify",
    "generate_token", "generate_hex",
    "encrypt", "decrypt",
    "hash_password", "verify_password",
]
