"""
SENTINEL — Auth Routes
=========================
POST /auth/login: exchanges username/password for a signed JWT.
GET  /auth/me:    lets the frontend validate a stored token (and read
                   back its role) without guessing at expiry client-side.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import LoginRequest
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.core.users import authenticate

router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    role = authenticate(payload.username, payload.password)
    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(subject=payload.username, role=role)
    return {"access_token": token, "token_type": "bearer", "role": role, "username": payload.username}


@router.get("/auth/me")
def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return user
