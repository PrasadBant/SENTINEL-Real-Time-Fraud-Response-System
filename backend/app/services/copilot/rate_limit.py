"""
SENTINEL — Copilot Rate Limiter
===================================
Lightweight, in-memory, per-user sliding-window rate limit for
POST /api/copilot/chat — the one copilot route that can trigger a paid
LLM API call and real investigative actions (freeze/close), so it's the
one worth protecting against a runaway client or scripted abuse.

No external dependency (Redis, slowapi): this mirrors the rest of the
app's single-process, in-memory-state style (see
app.services.withdrawal_tracker for the same pattern applied to
EC-03's withdrawal timers). Like the ephemeral SECRET_KEY documented in
app/core/config.py, this is not safe across multiple worker processes
or a restart — acceptable for this app's current single-process
deployment model; swap for a Redis-backed limiter (e.g. via slowapi)
if SENTINEL is ever run with multiple workers.
"""

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user

# Generous enough for normal back-and-forth investigation chat, tight
# enough to blunt a scripted loop hammering the LLM provider.
MAX_REQUESTS_PER_WINDOW = 30
WINDOW_SECONDS = 60

# username -> timestamps (monotonic clock, immune to system-clock changes)
# of requests within the current rolling window.
_hits: dict[str, deque[float]] = defaultdict(deque)


def _check_and_record(username: str) -> None:
    now = time.monotonic()
    window = _hits[username]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    if len(window) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: max {MAX_REQUESTS_PER_WINDOW} copilot "
                f"messages per {WINDOW_SECONDS}s. Please wait and try again."
            ),
        )
    window.append(now)


async def rate_limited_user(user: dict = Depends(get_current_user)) -> dict:
    """
    Drop-in replacement for get_current_user on rate-limited routes:
    resolves the same user dict (so route handlers don't change), but
    raises 429 first if this user has exceeded the copilot chat rate
    limit. Keyed by username, not IP — multiple investigators can share
    an office network without throttling each other, and one
    compromised/scripted account can't hide behind that shared IP either.
    """
    _check_and_record(user.get("username") or "unknown")
    return user


def reset() -> None:
    """
    Clears every user's recorded request timestamps. The application
    itself never calls this — it exists for tests. The whole backend
    test suite reuses the same two demo accounts (admin/viewer) across
    dozens of copilot tests spread over several files, all executing
    within the same real-world minute; without a reset between tests,
    the shared quota exhausts partway through the suite and later,
    unrelated tests start failing with 429s that have nothing to do with
    what they're actually testing. See tests/conftest.py's autouse
    fixture, which calls this before every test.
    """
    _hits.clear()
