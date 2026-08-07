"""
SENTINEL — Password Hashing & JWT Helpers
============================================
Stdlib-only password hashing (PBKDF2-HMAC-SHA256, random salt per user —
no bcrypt/passlib dependency needed) plus PyJWT for signed, expiring
access tokens.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY

_PBKDF2_ITERATIONS = 260_000
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Returns 'salt_hex$digest_hex'."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, digest_hex = hashed.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    # Constant-time comparison — avoids leaking hash-match progress via timing.
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Returns the decoded claims, or None if the token is invalid/expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
