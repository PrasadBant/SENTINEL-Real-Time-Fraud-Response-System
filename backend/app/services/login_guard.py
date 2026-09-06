"""
SENTINEL — Login Brute-Force Guard
=====================================
Redis-backed failed-login counter for POST /auth/login, keyed by
username (not IP — this deployment has no reliable client IP today, and
a shared demo/investigator-room setup would make IP-based lockout lock
out everyone behind the same NAT together). Locking by username instead
means an attacker COULD grief a known username into lockout by
deliberately failing its login repeatedly — an accepted trade-off for
the "minimal track" (see the Phase 2 build plan); a real deployment
wanting IP-awareness too would combine both keys, not swap one for the
other.

Fails OPEN, not closed, on a Redis outage (same posture as every other
Redis-dependent path since Phase 1's hostile-review fixes — see
app/services/orchestrator.py): a Redis outage must degrade to
"brute-force lockout temporarily unenforced," not "nobody can log in."
Losing lockout enforcement during a Redis outage is a much smaller risk
than turning a Redis outage into a full authentication outage.
"""

import logging

from app.core import redis_client
from app.core.config import LOGIN_LOCKOUT_SECONDS, LOGIN_MAX_ATTEMPTS

logger = logging.getLogger("sentinel.login_guard")


def _key(username: str) -> str:
    return f"sentinel:loginfail:{username}"


def is_locked_out(username: str) -> bool:
    """True if `username` has hit LOGIN_MAX_ATTEMPTS failures within the
    current LOGIN_LOCKOUT_SECONDS window. Degrades to False (not locked
    out) if Redis is unreachable — see module docstring."""
    try:
        raw = redis_client.get_redis().get(_key(username))
        return raw is not None and int(raw) >= LOGIN_MAX_ATTEMPTS
    except Exception as e:
        logger.warning("is_locked_out degraded for %s (Redis unavailable: %s) — treating as not locked out", username, e)
        return False


def record_failure(username: str) -> None:
    """Increment the failure counter, starting a fresh LOGIN_LOCKOUT_SECONDS
    window on the first failure. Best-effort — a failure here must never
    block the (already-failed) login response from returning."""
    try:
        r = redis_client.get_redis()
        key = _key(username)
        count = r.incr(key)
        if count == 1:
            r.expire(key, LOGIN_LOCKOUT_SECONDS)
    except Exception as e:
        logger.warning("record_failure degraded for %s (Redis unavailable: %s)", username, e)


def clear(username: str) -> None:
    """Reset the failure counter on a successful login. Best-effort, same
    reasoning as record_failure."""
    try:
        redis_client.get_redis().delete(_key(username))
    except Exception as e:
        logger.warning("clear degraded for %s (Redis unavailable: %s)", username, e)
