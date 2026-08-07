from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class Transaction(BaseModel):
    """
    Incoming transaction payload for POST /transaction.

    `extra="allow"` is intentional: the simulator and scoring engine pass a
    long tail of optional risk-signal flags (is_cross_border, device_changed,
    on_active_call, velocity_flag, ...) that aren't meaningful to validate
    strictly here. This model's job is to guarantee the handful of fields the
    pipeline actually depends on are present and well-typed; everything else
    rides along unvalidated, same as before.
    """

    model_config = ConfigDict(extra="allow")

    tx_id: str = Field(min_length=1)
    sender_account: str = Field(min_length=1)
    receiver_account: str = Field(min_length=1)
    amount: float = Field(gt=0)
    timestamp: datetime
    channel: str = Field(min_length=1)
    currency: Optional[str] = "INR"
    hop_number: Optional[int] = 0
    risk_score: Optional[float] = None
    case_id: Optional[str] = None
