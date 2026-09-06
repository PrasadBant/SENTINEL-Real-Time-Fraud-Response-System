"""
SENTINEL — Structured Logging
================================
Replaces the print()-with-a-bracketed-tag convention used across the
codebase (e.g. "  [Orchestrator] ...", "  [EC-03] ...") with real
`logging` calls on a per-component logger (`sentinel.<component>`) and a
single JSON-line formatter, so log output is machine-parseable and every
line carries the correlation ID of the request/job it belongs to.

Usage in any module:
    import logging
    logger = logging.getLogger("sentinel.<component>")
    logger.info("...")

Every "sentinel.*" logger propagates up to the "sentinel" root logger
configured here — no per-module handler setup needed.
"""

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

# Set at the top of POST /transaction (app/api/transactions.py) and
# re-set at the start of the EC-03 job body (app/services/
# withdrawal_simulator.py's run_withdrawal_job) — NOT relied on to
# propagate automatically across that second boundary: a contextvar
# survives an asyncio.create_task() (the Context is copied at task
# creation), but not a job that's persisted to Redis and picked up by a
# possibly-later, possibly-different execution of the worker loop. The
# job receives correlation_id as an explicit argument instead and sets
# this itself.
CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": CORRELATION_ID.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Call once, as early as possible (before any app.* import — several
    modules log a warning at import time, e.g. app.core.config's
    SECRET_KEY fallback, and those lines should be JSON too, not fall
    back to Python's default unconfigured-logger stderr output)."""
    root = logging.getLogger("sentinel")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False
