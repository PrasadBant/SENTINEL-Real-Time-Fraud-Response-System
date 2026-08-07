"""SENTINEL — WebSocket endpoint. Push-only: broadcasts are sent by other routers via `manager`."""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.deps import get_ws_user
from app.websocket.connection_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user: dict = Depends(get_ws_user)) -> None:
    # Browsers can't set custom headers on a WS handshake, so auth travels as
    # a query param: ws://host/ws?token=<jwt>. get_ws_user rejects the
    # handshake before we ever accept() if the token is missing/invalid.
    await manager.connect(websocket)
    try:
        await websocket.send_json({"event": "connected", "status": "LIVE"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
