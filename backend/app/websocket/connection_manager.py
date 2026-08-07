"""
SENTINEL — WebSocket Connection Manager
=========================================
Tracks connected dashboard clients and broadcasts events to all of them.
A single module-level `manager` instance is shared across every router
that needs to push live updates (transactions, cases, actions).
"""

from typing import Any
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections = [ws for ws in self.active_connections if ws is not websocket]

    async def broadcast(self, message: dict[str, Any]) -> None:
        failed: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                failed.append(ws)
        for ws in failed:
            self.disconnect(ws)


# Shared singleton — every router imports this same instance.
manager = ConnectionManager()
