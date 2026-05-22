from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from pydantic import model_validator
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
    role: str = Field(default="worker", index=True)  # worker, master, support, sales, listener, collector, main
    tier: Optional[str] = Field(default="tier3", index=True)  # tier1 (premium), tier2 (support/shill), tier3 (disposable)
    tags: Optional[str] = None  # Comma separated tags e.g. "US,Crypto"
    
    # 战斗角色 (Strategic Combat Role)
    combat_role: str = Field(default="cannon", index=True)  # cannon(炮灰)/scout(侦察)/actor(演员)/sniper(狙击)
    health_score: int = Field(default=100, index=True)  # 健康分 0-100
    daily_action_count: int = Field(default=0)  # 今日操作次数
    last_error_type: Optional[str] = None  # 最后错误类型

    # AI 人设绑定（用于 trigger_ai 炒群、自动回复）
    ai_persona_id: Optional[int] = Field(default=None, foreign_key="ai_persona.id", index=True)

    # 多租户归属（TG1.AI 商业化）— NULL = 系统所有/未分配，仅 admin 视角可见
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id", index=True)

    # ── Epic 3: 客户激活后自动分配 + AI 改造 ──
    assigned_at: Optional[datetime] = Field(default=None, index=True)
    # AI 生成的行业匹配资料（DB-only；Epic 3.1 才真去 TG 上 set_username/set_bio）
    customized_username: Optional[str] = None
    customized_first_name: Optional[str] = None
    customized_last_name: Optional[str] = None
    customized_bio: Optional[str] = None
    # 若是替补账号，指向被替换的原账号（用于审计 + SLA 追踪）
    replaced_account_id: Optional[int] = Field(default=None, foreign_key="account.id", index=True)

    # ── Epic 5.0: 客户主号标识 ──
    # True = 客户扫码登录的个人主号；listener / allocation 自动排除，避免把客户私号当工人调度
    is_customer_main: bool = Field(default=False, index=True)
    # session_string 是否已用 session_encryption_service 加密（向后兼容存量明文 session）
    session_string_encrypted: bool = Field(default=False)

    # ── Phase G: account → sales user ownership ──
    # NULL = pooled (admin-managed); set = this sales user owns daily ops on
    # the account (run scrapes, join groups, attach monitor rules). Only
    # meaningful for accounts inside an is_internal_pool=true customer for
    # platform sales, or for accounts under a customer for customer sub-sales.
    # The dual kind is needed because user_id collides between User and
    # CustomerUser tables.
    assigned_to_sales_user_id: Optional[int] = Field(default=None, index=True)
    assigned_to_sales_kind: Optional[str] = Field(default=None, max_length=20)  # 'platform' | 'customer'


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
    usage_level: Optional[int] = None  # derived from role; UI display only
    # Allow role=None when serializing (AccountBase declares str, but
    # in-flight objects may carry None before DB constraint fires).
    role: Optional[str] = Field(default="worker", index=True)

    @model_validator(mode="after")
    def _set_usage_level(self) -> "AccountRead":
        if self.usage_level is None and self.role:
            from app.core.account_roles import usage_level_for_role
            self.usage_level = usage_level_for_role(self.role)
        return self
