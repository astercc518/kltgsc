from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class OperationLogBase(SQLModel):
    action: str # e.g., "create_account", "send_message"
    username: str # operator username (if auth enabled) or "system"
    details: Optional[str] = None
    ip_address: Optional[str] = None
    status: str = Field(default="success")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class OperationLog(OperationLogBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class OperationLogCreate(OperationLogBase):
    pass

class OperationLogRead(OperationLogBase):
    id: int
