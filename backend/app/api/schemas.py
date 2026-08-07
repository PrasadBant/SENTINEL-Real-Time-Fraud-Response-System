"""Request body models shared across the API routers."""

from pydantic import BaseModel


class ActionRequest(BaseModel):
    case_id: str
    account_id: str | None = None
    target_id: str | None = None
    reason: str | None = None


class CopilotRequest(BaseModel):
    message: str
    context_case_id: str | None = None
