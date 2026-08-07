"""Request body models shared across the API routers."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class ActionRequest(BaseModel):
    case_id: str
    account_id: str | None = None
    target_id: str | None = None
    reason: str | None = None


class CopilotRequest(BaseModel):
    message: str
    context_case_id: str | None = None
    # Continues an existing chat thread (see app/services/copilot/history.py).
    # Omitted/unknown/belonging to another user -> a new conversation is
    # started transparently; the response always carries the ID that was
    # actually used.
    conversation_id: str | None = None
