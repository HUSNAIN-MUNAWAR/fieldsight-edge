from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def hash_secret(secret: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 210_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        _, salt, expected = stored.split("$", 2)
    except ValueError:
        return False
    actual = hash_secret(secret, salt).split("$", 2)[2]
    return hmac.compare_digest(actual, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(prefix: str = "fs") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def expires_in(hours: int = 8) -> datetime:
    return now() + timedelta(hours=hours)
