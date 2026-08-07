import os
import secrets as _secrets

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
WITHDRAWAL_DELAY_SECONDS = 40

# --- AUTH ---
# JWT signing key. Falls back to a random key generated at process start if
# unset — fine for a single dev session, but tokens won't survive a restart
# and won't be valid across multiple worker processes. Set SECRET_KEY in
# .env for anything beyond local demo use.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = _secrets.token_hex(32)
    print("  [WARNING] SECRET_KEY not set — using an ephemeral key generated at "
          "startup. Existing login tokens will be invalidated on every restart. "
          "Set SECRET_KEY in backend/.env for stable sessions.")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8h shift

# Static key checked on POST /transaction — ingestion is a machine-to-machine
# feed (the simulator script), not a logged-in user, so it uses a simple
# shared secret rather than a JWT. Change this in any non-local deployment.
SIMULATOR_API_KEY = os.getenv("SIMULATOR_API_KEY", "sentinel-dev-simulator-key")

