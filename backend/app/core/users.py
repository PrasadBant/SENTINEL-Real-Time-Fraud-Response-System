"""
SENTINEL — User Store
========================
Phase 2: login accounts are now a real (if minimal) DB-backed table
(app.core.db_models.UserRecord) instead of an in-memory dict rebuilt from
env vars on every process start. ADMIN_USERNAME/PASSWORD and
VIEWER_USERNAME/PASSWORD remain how the two default accounts are
*bootstrapped* (see app.core.repository.seed_default_users(), called
once from main.py's lifespan) — but from then on the DB row is the
durable source of truth, not these constants: a restart no longer
silently re-derives credentials from whatever the env vars currently
say, and (unlike the old model) more accounts/tenants can exist beyond
these first two, provisioned directly in the DB.

Credentials must still be supplied via ADMIN_PASSWORD/VIEWER_PASSWORD —
the app refuses to start without them, rather than falling back to a
guessable default (the old admin123/viewer123 pair the frontend used to
hardcode client-side, before this was hashed and checked server-side).
"""

import os

from app.core.security import verify_password

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


def authenticate(username: str, password: str) -> tuple[str, str] | None:
    """Returns (role, tenant_id) if the credentials are valid, else None.

    Deferred import of the repository singleton (not a module-level
    import): app.core.repository imports app.core.users back (inside
    seed_default_users(), itself deferred for the same reason) to read
    these ADMIN_USERNAME/PASSWORD constants — a top-level
    `users -> repository -> users` cycle would make one of the two fail
    to import. Deferring this one breaks the cycle without changing
    behavior, matching repository.py's own documented pattern for its
    orchestrator import."""
    from app.core.repository import repository

    user = repository.get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    repository.touch_last_login(username)
    return user["role"], user["tenant_id"]
