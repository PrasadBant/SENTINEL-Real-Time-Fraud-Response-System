"""
Phase 2 (Security & Observability) — Redis-backed brute-force lockout on
POST /auth/login (app/services/login_guard.py). Runs against fakeredis by
default (see conftest.py) — fakeredis correctly implements INCR/EXPIRE
semantics, which is all this module needs.
"""

from app.core.config import LOGIN_MAX_ATTEMPTS
from app.core.repository import repository
from app.core.security import hash_password
from app.services import login_guard


def _seed_user(username: str) -> None:
    repository.create_user(username, hash_password("correct-password"), "viewer")


def test_lockout_after_max_attempts_blocks_even_the_correct_password(client):
    username = "lockout-subject-a"
    _seed_user(username)
    login_guard.clear(username)  # isolate from any earlier test's counter

    for _ in range(LOGIN_MAX_ATTEMPTS):
        r = client.post("/auth/login", json={"username": username, "password": "wrong"})
        assert r.status_code == 401

    # One more attempt, this time with the CORRECT password — must still
    # be rejected, with 429 (not 401), since the account is now locked out.
    r = client.post("/auth/login", json={"username": username, "password": "correct-password"})
    assert r.status_code == 429


def test_successful_login_clears_the_failure_counter(client):
    username = "lockout-subject-b"
    _seed_user(username)
    login_guard.clear(username)

    for _ in range(LOGIN_MAX_ATTEMPTS - 1):
        client.post("/auth/login", json={"username": username, "password": "wrong"})

    # One failure short of lockout — a correct login now must succeed and
    # reset the counter.
    r = client.post("/auth/login", json={"username": username, "password": "correct-password"})
    assert r.status_code == 200

    # Confirm the counter was actually reset, not just "not yet at the
    # threshold": another full run of failures should need the full
    # LOGIN_MAX_ATTEMPTS again before locking out.
    for _ in range(LOGIN_MAX_ATTEMPTS - 1):
        r = client.post("/auth/login", json={"username": username, "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/auth/login", json={"username": username, "password": "correct-password"})
    assert r.status_code == 200, "counter should have been cleared by the earlier successful login"


def test_lockout_is_scoped_per_username(client):
    """A different username's failures must not lock out this one — the
    guard is keyed by username, not global."""
    victim = "lockout-subject-c"
    attacker_target = "lockout-subject-d"
    _seed_user(victim)
    _seed_user(attacker_target)
    login_guard.clear(victim)
    login_guard.clear(attacker_target)

    for _ in range(LOGIN_MAX_ATTEMPTS):
        client.post("/auth/login", json={"username": attacker_target, "password": "wrong"})

    r = client.post("/auth/login", json={"username": victim, "password": "correct-password"})
    assert r.status_code == 200


def test_concurrent_failed_logins_cannot_exceed_max_attempts(client):
    """Phase 2 hostile-review fix (MEDIUM-HIGH, TOCTOU race): the old
    is_locked_out()-then-record_failure() split let concurrent requests
    all read the counter's stale value before any of their own
    increments landed — live-verified with 20 simultaneous wrong-password
    requests against one username: 20x401, 0x429, none blocked at all.
    Fires the identical attack here and asserts AT MOST LOGIN_MAX_ATTEMPTS
    of them ever reach authenticate() (i.e. get a 401, meaning they were
    allowed through) — the rest must be rejected with 429, regardless of
    thread interleaving. This is the "green test that doesn't prove the
    property" the sequential tests above were — those loop one request at
    a time and could never have caught this race."""
    import threading

    username = "lockout-concurrent-subject"
    _seed_user(username)
    login_guard.clear(username)

    n_concurrent = 20
    results: list[int] = []
    results_lock = threading.Lock()

    def attempt():
        r = client.post("/auth/login", json={"username": username, "password": "wrong"})
        with results_lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=attempt) for _ in range(n_concurrent)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allowed_through = results.count(401)  # reached authenticate() and failed on password
    rejected = results.count(429)  # blocked by the lockout guard before authenticate()

    assert allowed_through + rejected == n_concurrent, f"unexpected status codes: {results}"
    assert allowed_through <= LOGIN_MAX_ATTEMPTS, (
        f"{allowed_through} of {n_concurrent} concurrent attempts reached authenticate() — "
        f"expected at most LOGIN_MAX_ATTEMPTS ({LOGIN_MAX_ATTEMPTS}); the atomic guard failed "
        f"to serialize concurrent requests. Full results: {results}"
    )
    assert rejected >= n_concurrent - LOGIN_MAX_ATTEMPTS

    # And the lockout it established must actually hold afterward, even
    # for the correct password.
    r = client.post("/auth/login", json={"username": username, "password": "correct-password"})
    assert r.status_code == 429


def test_login_guard_fails_open_when_redis_unavailable(client, monkeypatch):
    """A Redis outage must degrade to "lockout temporarily unenforced,"
    not "nobody can log in" — see login_guard.py's module docstring."""
    from app.core import redis_client

    class _BrokenRedis:
        def __getattr__(self, _name):
            def _raise(*_a, **_kw):
                raise ConnectionError("simulated Redis outage")
            return _raise

    monkeypatch.setattr(redis_client, "get_redis", lambda: _BrokenRedis())

    username = "lockout-subject-e"
    _seed_user(username)
    r = client.post("/auth/login", json={"username": username, "password": "correct-password"})
    assert r.status_code == 200
