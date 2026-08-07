"""
SENTINEL — Auth Dependencies
===============================
FastAPI dependencies for bearer-token verification (HTTP routes),
role gating, WebSocket token verification, and the simulator's
static API-key check on POST /transaction.
"""

import hmac

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import SIMULATOR_API_KEY
from app.core.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Requires a valid 'Authorization: Bearer <token>' header. Any role."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return {"username": payload.get("sub"), "role": payload.get("role")}


def require_role(*roles: str):
    """Dependency factory: requires a valid token AND one of the given roles."""

    async def _checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker


async def get_ws_user(token: str = Query(...)) -> dict:
    """
    Browsers can't set custom headers on a WebSocket handshake, so the
    token travels as a query param instead: ws://host/ws?token=<jwt>.
    Raising HTTPException here causes FastAPI to reject the handshake
    before accept() is called.
    """
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return {"username": payload.get("sub"), "role": payload.get("role")}


async def verify_simulator_key(request: Request) -> None:
    """
    Gate for POST /transaction: the simulator is a standalone script with
    no user login, so it authenticates with a static shared key (header
    'X-API-Key') rather than a JWT.
    """
    provided = request.headers.get("X-API-Key", "")
    if not provided or not hmac.compare_digest(provided, SIMULATOR_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-Key")
