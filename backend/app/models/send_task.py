from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class SendTaskBase(SQLModel):
    name: str
    message_content: str
    status: str = Field(default="pending")  # pending, running, completed, failed, paused
    total_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    min_delay: int = 10  # Minimum delay in seconds
    max_delay: int = 60  # Maximum delay in seconds

class SendTask(SendTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relationships can be added here if we want to link specific accounts/targets strictly
    # For now, we might store IDs as JSON string or handle logic separately to avoid complex M2M tables initially, 
    # OR we use a separate table for execution details.

class SendTaskCreate(SendTaskBase):
    account_ids: List[int]
    target_user_ids: List[int]

class SendTaskRead(SendTaskBase):
    id: int

class SendRecordBase(SQLModel):
    task_id: int = Field(foreign_key="sendtask.id")
    account_id: int = Field(foreign_key="account.id")
    target_user_id: int = Field(foreign_key="targetuser.id")
    status: str  # success, failed
    error_message: Optional[str] = None
    sent_at: datetime = Field(default_factory=datetime.utcnow)

class SendRecord(SendRecordBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
