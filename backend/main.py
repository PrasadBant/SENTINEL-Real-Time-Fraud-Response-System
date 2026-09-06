"""
SENTINEL — Application Entrypoint
====================================
Thin app factory: creates the FastAPI app, wires up middleware/exception
handling, mounts every route module, and runs startup/shutdown hooks.
All actual route logic lives under app/api/; shared state (WebSocket
connections) lives under app/websocket/.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

# Must run before any other app.* import: several modules log a line at
# import time (e.g. app.core.config's SECRET_KEY fallback warning), and
# those should come out as JSON too, not fall through to Python's
# default unconfigured-logger stderr output. app.core.logging_config
# itself doesn't import app.core.config, so this is safe to do first.
from app.core.logging_config import configure_logging
configure_logging()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import actions, attack_mode, auth, cases, copilot, health, transactions, ws_routes
from app.core import metrics
from app.core.config import EC03_QUEUE_ENABLED, REDIS_URL
from app.core.data_store import data_store
from app.core.database import run_migrations
from app.core.repository import repository
from app.websocket.connection_manager import manager

logger = logging.getLogger("sentinel")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Bring the schema up to date (Alembic) and restore in-memory state
    from the database on startup."""
    run_migrations()
    # Phase 2: bootstrap the DB-backed admin/viewer accounts from
    # ADMIN_USERNAME/PASSWORD + VIEWER_USERNAME/PASSWORD if they don't
    # already exist — see repository.seed_default_users()'s docstring for
    # why this is idempotent-by-design rather than a one-time migration
    # data load.
    repository.seed_default_users()
    repository.load_all(data_store)

    # Redis pub/sub fanout listener (see app/websocket/connection_manager.py)
    # — must be running before any client connects, so it's started here
    # rather than lazily on first broadcast.
    listener_task = asyncio.create_task(manager.listen())

    # Spawn Phase 4: Global Graph Analytics background task
    from app.services.global_graph_analyzer import run_global_graph_analyzer
    analyzer_task = asyncio.create_task(run_global_graph_analyzer(manager, data_store))

    # Embedded EC-03 job worker (see app/services/withdrawal_queue.py /
    # withdrawal_simulator.py for why this runs in-process rather than as
    # a separate container). Gated by the same EC03_QUEUE_ENABLED flag
    # withdrawal_queue.py's schedule()/cancel() check, so tests (which
    # set it false) never spin this up against a Redis that isn't there.
    worker_task = None
    if EC03_QUEUE_ENABLED:
        from arq.connections import RedisSettings
        from arq.worker import Worker
        from app.services.withdrawal_simulator import run_withdrawal_job

        # handle_signals=False: Worker's default (True) installs its own
        # SIGINT/SIGTERM handlers via the event loop, which would fight
        # with uvicorn's own shutdown handling in this same process on
        # Linux (the real deployment target) — arq's own signal-handler
        # code degrades harmlessly on Windows (catches the platform's
        # NotImplementedError), so this only matters there, but Linux is
        # what matters for correctness.
        worker = Worker(
            functions=[run_withdrawal_job],
            redis_settings=RedisSettings.from_dsn(REDIS_URL),
            allow_abort_jobs=True,
            max_tries=3,
            handle_signals=False,
        )
        worker_task = asyncio.create_task(worker.async_run())

    yield

    analyzer_task.cancel()
    listener_task.cancel()
    if worker_task is not None:
        worker_task.cancel()
        # Deliberately NOT calling worker.close(): verified by direct
        # testing that it unconditionally references signal.SIGUSR1
        # (arq/worker.py), which doesn't exist on Windows, and would
        # crash shutdown here. Skipping it leaks the worker's Redis
        # connection pool briefly — harmless, the process is exiting.


app = FastAPI(title="SENTINEL - Real-Time Fraud Response System", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all safety net: any exception that isn't an intentional HTTPException
    (those are handled separately by FastAPI's default handler) is logged
    server-side and reported to the client as a generic 500 — never leaking
    stack traces, file paths, or internal state.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again or contact support."},
    )


# CORS_ORIGINS: comma-separated list of allowed frontend origins.
# Defaults to the local Vite dev server. Wildcard ("*") is intentionally
# NOT supported together with allow_credentials=True — browsers reject
# that combination, and permitting it would expose the API to any origin.
_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    """Phase 2: records request count/latency for GET /metrics. Uses
    request.url.path (not route.path) as the label — with no path-param
    routes in this API today (case/tx ids travel in the body, not the
    URL), this doesn't create a label-cardinality blowup; worth
    revisiting if that ever changes."""
    with metrics.HTTP_REQUEST_DURATION_SECONDS.labels(request.method, request.url.path).time():
        response = await call_next(request)
    metrics.HTTP_REQUESTS_TOTAL.labels(request.method, request.url.path, response.status_code).inc()
    return response


# ── Routes ──────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(cases.router)
app.include_router(actions.router)
app.include_router(attack_mode.router)
app.include_router(copilot.router)
app.include_router(ws_routes.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, env_file=".env")
