from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime

class WarmupTaskBase(SQLModel):
    name: str
    action_type: str = Field(default="mixed") # mixed, view_channel, reaction
    status: str = Field(default="pending")  # pending, running, completed, failed
    account_ids_json: str = "[]" # Store IDs as JSON string since we don't have M2M table yet
    min_delay: int = 5
    max_delay: int = 30
    duration_minutes: int = 30 # How long to run per account
    target_channels: str = "" # Comma separated list of channels to browse
    created_at: datetime = Field(default_factory=datetime.utcnow)
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    error_message: Optional[str] = None

class WarmupTask(WarmupTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class WarmupTaskCreate(WarmupTaskBase):
    account_ids: List[int]

class WarmupTaskRead(WarmupTaskBase):
    id: int
    account_ids: List[int]
