from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class WarmupTemplateBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    action_type: str = Field(default="mixed")  # mixed, view_channel, reaction
    min_delay: int = 5
    max_delay: int = 30
    duration_minutes: int = 30
    target_channels: str = ""  # Comma separated list of channels
    is_default: bool = Field(default=False)  # 默认模板

class WarmupTemplate(WarmupTemplateBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class WarmupTemplateCreate(WarmupTemplateBase):
    pass

class WarmupTemplateUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    action_type: Optional[str] = None
    min_delay: Optional[int] = None
    max_delay: Optional[int] = None
    duration_minutes: Optional[int] = None
    target_channels: Optional[str] = None
    is_default: Optional[bool] = None

class WarmupTemplateRead(WarmupTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
