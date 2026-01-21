from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class InviteTaskBase(SQLModel):
    name: str
    target_channel: str # The channel/group to invite users TO
    source_group: Optional[str] = None # Optional: used for filtering targets
    status: str = Field(default="pending") # pending, running, completed, failed, paused
    
    account_ids_json: str = "[]" # List of account IDs to use for inviting
    target_user_ids_json: str = "[]" # List of target user IDs to invite
    
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    
    min_delay: int = 5
    max_delay: int = 15
    max_invites_per_account: int = 5 # Safety limit

    created_at: datetime = Field(default_factory=datetime.utcnow)

class InviteTask(InviteTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class InviteTaskCreate(InviteTaskBase):
    account_ids: List[int]
    target_user_ids: List[int]
    
class InviteTaskRead(InviteTaskBase):
    id: int
