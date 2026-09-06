import os

# --- RISK WEIGHTS (Normalized to sum = 1.0) ---
W_NEW_RECEIVER = 0.35
W_AMOUNT_DEV = 0.30
W_TIME_ANOMALY = 0.20
W_CALL_FLAG = 0.15

# --- THRESHOLDS ---
HIGH_RISK_THRESHOLD = 60
MEDIUM_THRESHOLD = 40

# --- SYSTEM CONFIG ---
DECAY_FACTOR = 0.85
GOLDEN_WINDOW_MINUTES = 20
# Was a bare hardcoded constant; every other value below it in this file
# is env-overridable, so this one-line fix just closes that inconsistency
# (Phase 1, landed alongside REDIS_URL below — not otherwise related).
WITHDRAWAL_DELAY_SECONDS = int(os.getenv("WITHDRAWAL_DELAY_SECONDS", "40"))

# --- REDIS (Phase 1: shared velocity/account state, WS pub/sub fanout,
# EC-03 job scheduling — see app/core/redis_client.py,
# app/services/orchestrator.py, app/websocket/connection_manager.py,
# app/services/withdrawal_queue.py) ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Gates both withdrawal_queue.schedule()/cancel() and the embedded Arq
# worker started in main.py's lifespan. Unlike velocity_cache/accounts/
# WS pub/sub (which go through app.core.redis_client, itself
# monkeypatched to fakeredis in tests — see tests/conftest.py),
# withdrawal_queue.py talks to Arq's own Redis pool directly, which
# fakeredis can't stand in for (Arq needs real atomic dequeue semantics).
# Without this flag, the default test suite would hit Arq's real
# connection-retry backoff (RedisSettings' default conn_retries=5,
# conn_retry_delay=1s) against a Redis that isn't there in CI/local test
# runs, on every HIGH_RISK-case test — schedule()/cancel() already
# degrade to a safe no-op on failure, but only after ~5s of retrying
# each time, which measurably slows the whole suite down. Defaulted true
# for real deployments; tests/conftest.py sets this false.
EC03_QUEUE_ENABLED = os.getenv("EC03_QUEUE_ENABLED", "true").lower() == "true"

# --- AUTH ---
# JWT signing key. Fail closed, not open (Phase 2): this used to fall
# back to a random key generated at process start with only a warning —
# tolerable for a single dev session, but now that the API actually
# scales to multiple replicas (Phase 1), an ephemeral per-process key
# would be silently broken in production: each replica would sign/verify
# with a DIFFERENT random key, so a token minted by replica A would be
# rejected by replica B, and every token would be invalidated on every
# restart regardless. Same fail-closed posture and wording style as
# ADMIN_PASSWORD/VIEWER_PASSWORD in app/core/users.py.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable must be set — refusing to start "
        "with an ephemeral, per-process key (it would silently break auth "
        "the moment more than one API replica exists, and invalidate every "
        "session on every restart). Generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\" "
        "— see .env.example."
    )

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8h shift

# --- LOGIN LOCKOUT (Phase 2: app/services/login_guard.py) ---
# Redis-backed, not per-process — the API scales to multiple replicas
# since Phase 1, and an in-memory counter would let an attacker bypass
# lockout just by hitting a different replica.
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))  # 15 min

# Static key checked on POST /transaction — ingestion is a machine-to-machine
# feed (the simulator script), not a logged-in user, so it uses a simple
# shared secret rather than a JWT. Change this in any non-local deployment.
SIMULATOR_API_KEY = os.getenv("SIMULATOR_API_KEY", "sentinel-dev-simulator-key")

