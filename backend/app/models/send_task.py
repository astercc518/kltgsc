from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class SendTaskBase(SQLModel):
    name: str
    message_content: str
    status: str = Field(default="pending", index=True)  # 添加索引用于筛选任务状态
    total_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)  # 添加索引
    min_delay: int = 10  # Minimum delay in seconds
    max_delay: int = 60  # Maximum delay in seconds


class SendTask(SendTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class SendTaskCreate(SendTaskBase):
    account_ids: List[int]
    target_user_ids: List[int]


class SendTaskRead(SendTaskBase):
    id: int


class SendRecordBase(SQLModel):
    task_id: int = Field(foreign_key="sendtask.id", index=True)  # 添加索引用于关联查询
    account_id: int = Field(foreign_key="account.id", index=True)  # 添加索引
    target_user_id: int = Field(foreign_key="targetuser.id", index=True)  # 添加索引
    status: str = Field(index=True)  # success, failed - 添加索引
    error_message: Optional[str] = None
    sent_at: datetime = Field(default_factory=datetime.utcnow, index=True)  # 添加索引用于时间查询


class SendRecord(SendRecordBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
