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
"""

import json
from typing import Any

from fastapi import WebSocket

from app.core import redis_client

CHANNEL = "sentinel:broadcast"


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
        below, even for the process that published (self-subscribe)."""
        await redis_client.get_async_redis().publish(CHANNEL, json.dumps(message, default=str))

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
        cancelled at shutdown."""
        pubsub = redis_client.get_async_redis().pubsub()
        await pubsub.subscribe(CHANNEL)
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
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()


# Shared singleton — every router imports this same instance.
manager = ConnectionManager()
