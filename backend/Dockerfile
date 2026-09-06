# SENTINEL backend — local/dev image for docker-compose's `api` service.
#
# Single-stage, matches CI's pinned Python exactly (see
# .github/workflows/ci.yml) so nothing here should behave differently
# from what's already tested there. Not production-hardened (no
# non-root user, no multi-stage slim-down, `--reload` left on) — that's
# explicitly out of scope for Phase 0 (see the build plan); this image
# exists to kill the "must run the backend directly on the host" problem,
# not to be a deploy artifact yet.
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Reuses the same entrypoint local dev already runs (`python main.py`),
# so there is no second "how does this actually start" code path to keep
# in sync — main.py's own __main__ block owns host/port/reload.
CMD ["python", "main.py"]
