from pydantic import BaseModel, Field, field_validator
from typing import List
from datetime import datetime

class AccountNode(BaseModel):
    account_id: str
    balance: float
    status: str
    linked_cases: List[str] = Field(default_factory=list)
    is_flagged: bool = False
    last_updated: datetime  # Must be timezone-aware (e.g., UTC)

    @field_validator('last_updated')
    @classmethod
    def ensure_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("last_updated must be timezone-aware")
        return v
