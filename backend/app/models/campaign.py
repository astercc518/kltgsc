"""
战役/项目模型
用于管理营销活动和任务聚合
"""
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class CampaignBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    status: str = Field(default="active", index=True)  # active/paused/completed
    
    # 资源配置
    allowed_roles: str = Field(default="cannon,scout")  # 允许使用的账号角色
    daily_budget: int = Field(default=1000)  # 每日消息上限
    daily_account_limit: int = Field(default=100)  # 每日账号消耗上限
    
    # AI 配置
    ai_persona_id: Optional[int] = Field(default=None, foreign_key="ai_persona.id")
    
    # 统计
    total_messages_sent: int = Field(default=0)
    total_replies_received: int = Field(default=0)
    total_conversions: int = Field(default=0)


class Campaign(CampaignBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CampaignCreate(SQLModel):
    name: str
    description: Optional[str] = None
    allowed_roles: str = "cannon,scout"
    daily_budget: int = 1000
    daily_account_limit: int = 100
    ai_persona_id: Optional[int] = None


class CampaignUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    allowed_roles: Optional[str] = None
    daily_budget: Optional[int] = None
    daily_account_limit: Optional[int] = None
    ai_persona_id: Optional[int] = None


class CampaignRead(CampaignBase):
    id: int
    created_at: datetime
    updated_at: datetime
