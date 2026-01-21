from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class ChatHistoryBase(SQLModel):
    account_id: int = Field(index=True, foreign_key="account.id")
    target_user_id: Optional[int] = Field(default=None, index=True) # ID from TargetUser table if applicable, or just raw telegram ID
    target_username: Optional[str] = None
    role: str = Field(default="user") # user (them) or assistant (us)
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatHistory(ChatHistoryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class ChatHistoryCreate(ChatHistoryBase):
    pass

class ChatHistoryRead(ChatHistoryBase):
    id: int
