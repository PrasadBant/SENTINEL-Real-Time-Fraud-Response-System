"""
SENTINEL — Demo User Store
=============================
A hackathon-scale, fixed two-account model (admin / viewer) matching the
two roles the frontend already gates its UI on. Credentials default to
the same admin123/viewer123 values the frontend used to hardcode
client-side (with zero server-side enforcement) — now hashed and checked
server-side instead. Override via env vars for any deployment beyond
local demo use; this is intentionally not a full user database.
"""

import os

from app.core.security import hash_password, verify_password

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
VIEWER_USERNAME = os.getenv("VIEWER_USERNAME", "viewer")
VIEWER_PASSWORD = os.getenv("VIEWER_PASSWORD", "viewer123")

_USERS: dict[str, dict[str, str]] = {
    ADMIN_USERNAME: {"password_hash": hash_password(ADMIN_PASSWORD), "role": "admin"},
    VIEWER_USERNAME: {"password_hash": hash_password(VIEWER_PASSWORD), "role": "viewer"},
}


def authenticate(username: str, password: str) -> str | None:
    """Returns the user's role if the credentials are valid, else None."""
    user = _USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user["role"]
