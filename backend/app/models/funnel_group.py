"""
营销群/私塘模型
管理自有群组（私域）
"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class FunnelGroupBase(SQLModel):
    link: str = Field(index=True)
    name: Optional[str] = None
    
    # 分类
    type: str = Field(default="nurture", index=True)  # filter/nurture/vip
    campaign_id: Optional[int] = Field(default=None, foreign_key="campaign.id", index=True)
    
    # 配置
    welcome_message: Optional[str] = None
    auto_kick_ads: bool = Field(default=True)
    
    # 统计
    member_count: int = Field(default=0)
    today_joined: int = Field(default=0)
    today_left: int = Field(default=0)


class FunnelGroup(FunnelGroupBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FunnelGroupCreate(SQLModel):
    link: str
    name: Optional[str] = None
    type: str = "nurture"
    campaign_id: Optional[int] = None
    welcome_message: Optional[str] = None


class FunnelGroupUpdate(SQLModel):
    name: Optional[str] = None
    type: Optional[str] = None
    campaign_id: Optional[int] = None
    welcome_message: Optional[str] = None
    auto_kick_ads: Optional[bool] = None


class FunnelGroupRead(FunnelGroupBase):
    id: int
    created_at: datetime
