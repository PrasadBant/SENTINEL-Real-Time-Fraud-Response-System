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

Phase 2 hostile-review fix (MEDIUM-HIGH, TOCTOU race): register_attempt()
below replaces what used to be two separate calls — is_locked_out() (a
GET) checked before authenticate(), then record_failure() (an INCR)
called after a failed one. That split left a window: concurrent
requests could all read the counter's pre-attack value before any of
their own increments landed, so a parallelized burst let far more than
LOGIN_MAX_ATTEMPTS guesses through before lockout ever engaged —
live-verified with 20 simultaneous wrong-password requests against one
username: 20x401, 0x429, none blocked. register_attempt() collapses the
check and the increment into ONE atomic Redis INCR call: every request
(successful or not) increments the SAME counter as its very first
action, and the INCR's own return value — guaranteed unique and
strictly increasing across any number of concurrent callers, since
Redis serializes INCR internally regardless of network-level
concurrency — is what decides whether this particular request is
allowed to proceed to authenticate() at all. There is no longer a
separate read step for an interleaved second request to observe stale
data through.
"""

import logging

from app.core import redis_client
from app.core.config import LOGIN_LOCKOUT_SECONDS, LOGIN_MAX_ATTEMPTS

logger = logging.getLogger("sentinel.login_guard")


def _key(username: str) -> str:
    return f"sentinel:loginfail:{username}"


def register_attempt(username: str) -> bool:
    """Atomically counts this login attempt against `username`'s window
    and returns whether it may proceed. Call this BEFORE checking the
    password at all — a request that comes back False must be rejected
    (429) without ever calling authenticate(), so a locked-out username
    gets no further verify_password() timing signal.

    Degrades to True (allowed) if Redis is unreachable — see module
    docstring."""
    try:
        r = redis_client.get_redis()
        key = _key(username)
        count = r.incr(key)
        if count == 1:
            # Only the request that actually created the key sets its
            # expiry — every subsequent INCR on an existing key leaves
            # its TTL untouched, exactly like the pre-fix code's
            # `if count == 1` guard (moved here, now the count that
            # decides this comes from the same atomic call, not a
            # separate GET).
            r.expire(key, LOGIN_LOCKOUT_SECONDS)
        return count <= LOGIN_MAX_ATTEMPTS
    except Exception as e:
        logger.warning("register_attempt degraded for %s (Redis unavailable: %s) — allowing through", username, e)
        return True


def clear(username: str) -> None:
    """Reset the attempt counter on a successful login. Best-effort, same
    fail-open reasoning as register_attempt."""
    try:
        redis_client.get_redis().delete(_key(username))
    except Exception as e:
        logger.warning("clear degraded for %s (Redis unavailable: %s)", username, e)
