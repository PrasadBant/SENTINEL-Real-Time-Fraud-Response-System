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

from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import actions, attack_mode, cases, copilot, health, transactions, ws_routes
from app.core.data_store import data_store
from app.core.database import init_db
from app.core.persistence import load_all_into_store
from app.websocket.connection_manager import manager

logger = logging.getLogger("sentinel")

app = FastAPI(title="SENTINEL - Real-Time Fraud Response System")


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


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize the database and restore in-memory state from SQLite."""
    init_db()
    load_all_into_store(data_store)

    # Spawn Phase 4: Global Graph Analytics background task
    from app.services.global_graph_analyzer import run_global_graph_analyzer
    asyncio.create_task(run_global_graph_analyzer(manager, data_store))


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

# ── Routes ──────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(transactions.router)
app.include_router(cases.router)
app.include_router(actions.router)
app.include_router(attack_mode.router)
app.include_router(copilot.router)
app.include_router(ws_routes.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, env_file=".env")
