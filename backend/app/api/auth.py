"""
SENTINEL — Auth Routes
=========================
POST /auth/login: exchanges username/password for a signed JWT. Gated by
app.services.login_guard's Redis-backed brute-force lockout (Phase 2).
GET  /auth/me:    lets the frontend validate a stored token (and read
                   back its role/tenant) without guessing at expiry
                   client-side.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import LoginRequest
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.core.users import authenticate
from app.services import login_guard

router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    # Atomically counts this attempt and checks it against the limit in
    # one step — see login_guard.register_attempt()'s docstring for why
    # this must be a single atomic call rather than a separate check
    # followed later by a separate increment (that split had a TOCTOU
    # race under concurrent requests, live-verified during the Phase 2
    # hostile review). A rejected attempt never reaches authenticate()
    # at all, so a locked-out username gets no verify_password() timing
    # signal either.
    if not login_guard.register_attempt(payload.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
        )

    result = authenticate(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    role, tenant_id = result
    login_guard.clear(payload.username)
    token = create_access_token(subject=payload.username, role=role, tenant_id=tenant_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "username": payload.username,
        "tenant_id": tenant_id,
    }


@router.get("/auth/me")
def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return user
