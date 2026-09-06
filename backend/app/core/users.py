"""
SENTINEL — Demo User Store
=============================
A hackathon-scale, fixed two-account model (admin / viewer) matching the
two roles the frontend already gates its UI on. Credentials must be
supplied via ADMIN_PASSWORD/VIEWER_PASSWORD — the app refuses to start
without them, rather than falling back to a guessable default (the old
admin123/viewer123 pair the frontend used to hardcode client-side, before
this was hashed and checked server-side). Override the usernames too via
env vars if you like; this is intentionally not a full user database.
"""

import os

from app.core.security import hash_password, verify_password

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
VIEWER_USERNAME = os.getenv("VIEWER_USERNAME", "viewer")
VIEWER_PASSWORD = os.getenv("VIEWER_PASSWORD")

# Fail closed, not open: usernames have benign defaults (they aren't
# secrets), but there is no safe default password. An unset password env
# var used to silently fall back to "admin123"/"viewer123" — a landmine
# for anyone who deploys this beyond a laptop demo without realizing it.
# Raising here (at import time, before the app can serve a single
# request) is deliberate: the alternative is prod running on prod being
# unlocked with the first the operator hears about it.
if not ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD environment variable must be set — refusing to "
        "start with a default/guessable admin password. See .env.example."
    )
if not VIEWER_PASSWORD:
    raise RuntimeError(
        "VIEWER_PASSWORD environment variable must be set — refusing to "
        "start with a default/guessable viewer password. See .env.example."
    )

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
