from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Transaction(BaseModel):
    tx_id: str
    sender_account: str
    receiver_account: str
    amount: float
    timestamp: datetime
    channel: str
    risk_score: Optional[float] = None
    case_id: Optional[str] = None
