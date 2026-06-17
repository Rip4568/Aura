"""Admin panel security helpers — password hashing and CSRF tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

PBKDF2_PREFIX = "pbkdf2_sha256$"
DEFAULT_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str, *, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> str:
    """Return a stored password hash using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"{PBKDF2_PREFIX}{iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify *password* against a PBKDF2 hash or legacy plain-text value."""
    if stored.startswith(PBKDF2_PREFIX):
        try:
            _, iterations_s, salt, expected_hex = stored.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations_s),
            )
            return hmac.compare_digest(digest.hex(), expected_hex)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(password, stored)


def ensure_csrf_token(session: dict[str, Any]) -> str:
    """Return the session CSRF token, creating one when missing."""
    token = session.get("admin_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return str(token)


def validate_csrf(session: dict[str, Any], submitted: str | None) -> bool:
    """Return True when *submitted* matches the session CSRF token."""
    expected = session.get("admin_csrf_token")
    if not expected or not submitted:
        return False
    return hmac.compare_digest(str(expected), submitted)
