from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from app.models.proxy import Proxy


class AccountBase(SQLModel):
    phone_number: str = Field(unique=True, index=True)
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    session_string: Optional[str] = None
    session_file_path: Optional[str] = None
    # 添加索引以加速状态筛选查询
    status: str = Field(default="init", index=True)  # init, active, banned, spam_block, flood_wait
    last_active: Optional[datetime] = Field(default=None, index=True)  # 添加索引
    proxy_id: Optional[int] = Field(default=None, foreign_key="proxy.id", index=True)  # 添加索引
    device_model: Optional[str] = None
    system_version: Optional[str] = None
    app_version: Optional[str] = None
    cooldown_until: Optional[datetime] = Field(default=None, index=True)  # 添加索引用于冷却查询
    
    # AI fields
    auto_reply: bool = Field(default=False, index=True)  # 添加索引用于筛选自动回复账号
    persona_prompt: Optional[str] = None  # e.g. "You are a helpful assistant..."
    
    # Management fields
    role: str = Field(default="worker", index=True)  # worker, master, support
    tier: Optional[str] = Field(default="tier3", index=True)  # tier1 (premium), tier2 (support/shill), tier3 (disposable)
    tags: Optional[str] = None  # Comma separated tags e.g. "US,Crypto"
    
    # 战斗角色 (Strategic Combat Role)
    combat_role: str = Field(default="cannon", index=True)  # cannon(炮灰)/scout(侦察)/actor(演员)/sniper(狙击)
    health_score: int = Field(default=100, index=True)  # 健康分 0-100
    daily_action_count: int = Field(default=0)  # 今日操作次数
    last_error_type: Optional[str] = None  # 最后错误类型


class Account(AccountBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)  # 添加索引用于排序
    
    proxy: Optional[Proxy] = Relationship(back_populates="accounts")

class AccountCreate(AccountBase):
    pass

class AccountRead(AccountBase):
    id: int
    created_at: datetime
    proxy: Optional[Proxy] = None
