from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

class Case(BaseModel):
    case_id: str
    status: str
    risk_score: float = 0.0
    transactions: List[str] = Field(default_factory=list)
    accounts: List[str] = Field(default_factory=list)
    created_at: datetime  # Must be timezone-aware (e.g., UTC)
    updated_at: datetime  # Must be timezone-aware (e.g., UTC)
    recoverable_amount: float = 0.0
    golden_window_minutes: int
    urgency_score: float = 0.0
    base_risk_score: float = 0.0

    @field_validator('created_at', 'updated_at')
    @classmethod
    def ensure_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("datetime fields must be timezone-aware")
        return v
