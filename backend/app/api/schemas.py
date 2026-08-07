"""Request body models shared across the API routers."""

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class ActionRequest(BaseModel):
    case_id: str
    account_id: str | None = None
    target_id: str | None = None
    reason: str | None = None


class CopilotRequest(BaseModel):
    # 2000 chars is generous for an investigator's question while keeping
    # the LLM prompt (and therefore latency/cost) bounded, and blocking
    # the classic DoS of pasting megabytes of text into a chat box.
    message: str = Field(min_length=1, max_length=2000)
    context_case_id: str | None = Field(default=None, max_length=64)
    # Continues an existing chat thread (see app/services/copilot/history.py).
    # Omitted/unknown/belonging to another user -> a new conversation is
    # started transparently; the response always carries the ID that was
    # actually used.
    conversation_id: str | None = Field(default=None, max_length=64)

    @field_validator("message")
    @classmethod
    def _reject_blank_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped
