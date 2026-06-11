"""Minimal username/password auth: PBKDF2 hashing + random bearer tokens.

Not enterprise-grade (no rate limiting, no refresh tokens), but real: passwords
are salted+hashed and never stored in plaintext, and each session is a random
opaque token stored server-side.
"""
from __future__ import annotations

import hashlib
import secrets

_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
    except (ValueError, AttributeError):
        return False
    calc = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return secrets.compare_digest(calc, h)


def new_token() -> str:
    return secrets.token_urlsafe(32)
