"""
流量源/猎场模型
管理目标群组（公海）
"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class SourceGroupBase(SQLModel):
    link: str = Field(index=True)
    name: Optional[str] = None
    
    # 分类
    type: str = Field(default="traffic", index=True)  # competitor/industry/traffic
    risk_level: str = Field(default="low")  # low/medium/high
    
    # 状态
    status: str = Field(default="active", index=True)  # active/exhausted/banned/honeypot
    member_count: int = Field(default=0)
    
    # 采集统计
    total_scraped: int = Field(default=0)
    high_value_count: int = Field(default=0)
    
    # AI 评估
    ai_score: Optional[int] = None
    ai_analysis: Optional[str] = None  # JSON

    # 多租户归属（TG1.AI 商业化）— NULL = 系统群组库，按行业筛选共享给客户
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id", index=True)

    # ── Epic 3: 按客户行业筛选 ──
    # crypto / ecommerce / b2b / gaming / mcn / other —— 与 Customer.industry 对齐
    industry: Optional[str] = Field(default=None, index=True, max_length=40)
    assigned_at: Optional[datetime] = Field(default=None, index=True)


class SourceGroup(SourceGroupBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    last_scraped_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SourceGroupCreate(SQLModel):
    link: str
    name: Optional[str] = None
    type: str = "traffic"
    risk_level: str = "low"


class SourceGroupUpdate(SQLModel):
    name: Optional[str] = None
    type: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
    ai_score: Optional[int] = None
    ai_analysis: Optional[str] = None


class SourceGroupRead(SourceGroupBase):
    id: int
    last_scraped_at: Optional[datetime]
    created_at: datetime
