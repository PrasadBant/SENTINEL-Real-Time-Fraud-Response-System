from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any
from datetime import datetime

class ActionLog(BaseModel):
    action_id: str
    case_id: str
    action_type: str
    target_id: str
    timestamp: datetime  # Must be timezone-aware (e.g., UTC)
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('timestamp')
    @classmethod
    def ensure_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v
