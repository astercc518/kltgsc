from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import BigInteger, Column, Text
from datetime import datetime


class TargetUserBase(SQLModel):
    telegram_id: int = Field(sa_column=Column(BigInteger, index=True, unique=True))  # BigInt避免溢出
    username: Optional[str] = Field(default=None, index=True)  # 添加索引用于按用户名搜索
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    source_group: Optional[str] = Field(default=None, index=True)  # 添加索引用于按来源筛选
    source_group_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, index=True))  # BigInt
    status: str = Field(default="new", index=True)  # new, contacted - 添加索引
    last_active: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)  # 添加索引
    
    # === 用户评分 ===
    engagement_score: int = Field(default=0, index=True)  # 互动评分 - 添加索引用于排序
    
    # === 营销阶段 ===
    marketing_stage: str = Field(default="new", index=True)  # 添加索引用于筛选
    
    # === 自动标签 ===
    tags: Optional[str] = None  # JSON 格式标签，如 ["price_sensitive", "high_intent"]
    
    # === 最后命中关键词 ===
    last_hit_keyword: Optional[str] = None
    last_hit_at: Optional[datetime] = Field(default=None, index=True)  # 添加索引
    
    # === AI 画像扩展 (STRATEGIC_PLAN 2.7) ===
    ai_score: Optional[int] = Field(default=None, index=True)  # AI评分 0-100
    ai_tags: Optional[str] = None  # AI生成的标签 JSON数组
    ai_summary: Optional[str] = None  # AI生成的用户摘要
    funnel_stage: str = Field(default="raw", index=True)  # raw/qualified/contacted/replied/converted
    
    # === 拉人状态 (批量邀请功能) ===
    invite_status: str = Field(default="untried", index=True)  
    # untried: 未尝试, success: 已成功拉入, privacy_restricted: 隐私限制, 
    # banned: 被封禁, not_mutual: 非双向联系人, other_error: 其他错误
    
    invite_target_group: Optional[str] = None  # 成功拉入的目标群
    invite_account_id: Optional[int] = Field(default=None, index=True)  # 执行拉人的账号ID
    invite_attempted_at: Optional[datetime] = Field(default=None, index=True)  # 最后尝试时间
    invite_success_at: Optional[datetime] = None  # 成功拉入时间
    invite_error_code: Optional[str] = None  # 错误代码，如 USER_PRIVACY_RESTRICTED
    invite_error_message: Optional[str] = Field(default=None, sa_column=Column(Text))  # 详细错误信息
    invite_attempt_count: int = Field(default=0)  # 尝试次数


class TargetUser(TargetUserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class TargetUserCreate(TargetUserBase):
    pass


class TargetUserRead(TargetUserBase):
    id: int


class TargetUserInviteUpdate(SQLModel):
    """更新用户邀请状态"""
    invite_status: str
    invite_target_group: Optional[str] = None
    invite_account_id: Optional[int] = None
    invite_error_code: Optional[str] = None
    invite_error_message: Optional[str] = None
