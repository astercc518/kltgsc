from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class TargetUserBase(SQLModel):
    telegram_id: int = Field(index=True)
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    source_group: Optional[str] = None # Link or ID of the group
    source_group_id: Optional[int] = None # Telegram Group ID
    status: str = Field(default="new") # new, contacted
    last_active: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # === 新增字段: 用户评分 ===
    engagement_score: int = Field(default=0)  # 互动评分 (基于关键词命中、回复等)
    
    # === 新增字段: 营销阶段 ===
    marketing_stage: str = Field(default="new")  # new, warm, qualified, converted, lost
    
    # === 新增字段: 自动标签 ===
    tags: Optional[str] = None  # JSON 格式标签，如 ["price_sensitive", "high_intent"]
    
    # === 新增字段: 最后命中关键词 ===
    last_hit_keyword: Optional[str] = None
    last_hit_at: Optional[datetime] = None

class TargetUser(TargetUserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class TargetUserCreate(TargetUserBase):
    pass

class TargetUserRead(TargetUserBase):
    id: int
