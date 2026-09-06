"""
SENTINEL — EC-03 Withdrawal Job Scheduling
==============================================
Replaces app/services/withdrawal_tracker.py's bare asyncio.Task tracking
(register/is_active/cancel over a module-level dict) with Arq, backed by
Redis: the schedule for "fire run_withdrawal_job for this case/node at
time T" now survives an API process restart, instead of vanishing
silently the moment the process that held the asyncio.Task dies.

Deliberately NOT a check-then-act pair of functions the way the old
tracker was (is_active() then separately register()) — Arq's own
`_job_id` dedup is atomic (see schedule() below), which is strictly
better than the old two-step pattern (harmless there only because
everything ran single-threaded in one process).

The worker that actually executes run_withdrawal_job runs embedded in
the same FastAPI process (see main.py's lifespan), not as a separate
container — see run_withdrawal_job's docstring in
app/services/withdrawal_simulator.py for why: its fire-time logic reads
app.core.data_store["graphs"], which isn't persisted or shared via Redis
today, so a genuinely separate worker process would have no way to see
it. Embedding still gets the real win here: the *schedule* is Redis-
backed and durable, only physical process separation is deferred.
"""

import asyncio
import logging

from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job

from app.core.config import EC03_QUEUE_ENABLED, REDIS_URL

logger = logging.getLogger("sentinel.ec03")

_pool = None
_pool_lock = asyncio.Lock()


async def _get_pool():
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:  # re-check: another caller may have won the race
                _pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    return _pool


async def schedule(key: str, case_id: str, suspect_node_id: str, delay_seconds: int, correlation_id: str) -> bool:
    """Enqueue run_withdrawal_job to fire in `delay_seconds`, keyed by
    `key` (the existing "{case_id}:{suspect_node_id}" scheme). Returns
    False if a job with this key is already scheduled/running (Arq's own
    _job_id dedup — atomic, no separate is_active() check needed) or if
    Redis is unreachable (logged, swallowed — matches
    app/core/repository.py's catch/log/continue style elsewhere)."""
    if not EC03_QUEUE_ENABLED:
        return False
    try:
        pool = await _get_pool()
        job = await pool.enqueue_job(
            "run_withdrawal_job",
            case_id, suspect_node_id, correlation_id,
            _job_id=key,
            _defer_by=delay_seconds,
        )
        return job is not None
    except Exception as e:
        logger.warning("schedule() failed for %s: %s", key, e)
        return False


async def cancel(key: str) -> bool:
    """Best-effort cancel of a pending withdrawal job. Not the only
    safeguard: run_withdrawal_job re-checks live node status at fire
    time regardless (see withdrawal_simulator.py) — that fire-time guard
    is the backstop if this cancel loses the race or Redis is briefly
    unreachable. Job.abort() actively waits for confirmation (it can
    hang if nothing's consuming the queue), so it's bounded with a
    timeout here rather than awaited unconditionally."""
    if not EC03_QUEUE_ENABLED:
        return False
    try:
        pool = await _get_pool()
        job = Job(job_id=key, redis=pool)
        return await job.abort(timeout=5.0)
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("cancel() timed out waiting for confirmation on %s", key)
        return False
    except Exception as e:
        logger.warning("cancel() failed for %s: %s", key, e)
        return False
