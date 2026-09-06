"""
SENTINEL — WebSocket Connection Manager
=========================================
Tracks connected dashboard clients and broadcasts events to all of them.
A single module-level `manager` instance is shared across every router
that needs to push live updates (transactions, cases, actions).

Each process's `active_connections` list is necessarily process-local —
a live WebSocket object can't cross a process boundary. What used to be
process-local *fanout* (broadcast() looping over that list directly) is
now Redis pub/sub: broadcast() only publishes, and every process
(including the one that published — a deliberate self-subscribe, so
there's no special-casing between "one replica" and "many replicas")
receives the message back through listen() and delivers it to its own
active_connections. This is what makes a broadcast from one API replica
actually reach a client connected to a different replica.

Both broadcast() and listen() are resilient to Redis being unreachable
(hostile-review findings): broadcast() logs and returns rather than
raising, so a Redis outage degrades live-update delivery instead of
turning every POST /transaction/action into a 500; listen() wraps its
subscribe loop in a bounded-exponential-backoff reconnect loop, since a
Redis restart was found (by direct reproduction — killing a live Redis
mid-stream) to kill the listener permanently otherwise — redis-py
resubscribes automatically on a *proactive* reconnect (the next command
issued through a connection) but does not resume an in-flight
`pubsub.listen()` generator after it raises ConnectionError.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

from app.core import redis_client

logger = logging.getLogger("sentinel.websocket")

CHANNEL = "sentinel:broadcast"

# Bounded exponential backoff for listen()'s reconnect loop.
_INITIAL_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections = [ws for ws in self.active_connections if ws is not websocket]

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Publish to Redis — delivery to local sockets happens in listen()
        below, even for the process that published (self-subscribe).

        Does not raise on a Redis failure: every caller (POST /transaction,
        the action endpoints, attack-mode, the EC-03 job, the global-graph
        analyzer) treats a broadcast as a best-effort side effect of work
        that already succeeded (scoring, a Postgres write, a freeze) — a
        lost live-update notification should never turn that success into
        an HTTP 500."""
        try:
            await redis_client.get_async_redis().publish(CHANNEL, json.dumps(message, default=str))
        except Exception as e:
            logger.warning("broadcast degraded (Redis unavailable): %s", e)

    async def _deliver_local(self, message: dict[str, Any]) -> None:
        """Fan out to this process's own connections only — the exact loop
        broadcast() used to run directly before Redis pub/sub fanout."""
        failed: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                failed.append(ws)
        for ws in failed:
            self.disconnect(ws)

    async def listen(self) -> None:
        """Long-running task (started in main.py's lifespan): subscribes to
        the broadcast channel and delivers every message — including this
        same process's own publishes — to local connections. Runs until
        cancelled at shutdown.

        Wrapped in an outer reconnect loop with bounded exponential
        backoff: a dropped/restarted Redis connection kills the inner
        `pubsub.listen()` generator (it raises ConnectionError rather than
        transparently resuming), so without this the whole live-update
        pipeline would die silently and permanently until the API process
        itself was restarted — confirmed by directly killing a live Redis
        mid-stream during testing. Each reconnect attempt re-creates the
        PubSub object and re-issues SUBSCRIBE from scratch, since the
        server-side subscription state is gone once the connection drops.
        """
        backoff = _INITIAL_RECONNECT_DELAY
        while True:
            try:
                pubsub = redis_client.get_async_redis().pubsub()
                await pubsub.subscribe(CHANNEL)
                logger.info("Subscribed to %s", CHANNEL)
                backoff = _INITIAL_RECONNECT_DELAY  # reset once a connection actually succeeds
                try:
                    async for msg in pubsub.listen():
                        if msg.get("type") != "message":
                            continue
                        try:
                            payload = json.loads(msg["data"])
                        except Exception:
                            continue
                        await self._deliver_local(payload)
                finally:
                    try:
                        await pubsub.unsubscribe(CHANNEL)
                        await pubsub.aclose()
                    except Exception:
                        pass  # connection may already be broken — nothing more to clean up
            except asyncio.CancelledError:
                # Deliberate shutdown (main.py cancels this task) — not a
                # connection failure. Let it propagate; do not "reconnect"
                # from a cancellation. (CancelledError subclasses
                # BaseException, not Exception, since Python 3.8, so the
                # `except Exception` below would never catch it anyway —
                # this branch is here to make that intent explicit rather
                # than rely on that fact being known.)
                raise
            except Exception as e:
                logger.warning(
                    "WS pub/sub listener disconnected (%s) — reconnecting in %.1fs",
                    e, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_RECONNECT_DELAY)


# Shared singleton — every router imports this same instance.
manager = ConnectionManager()
