"""
Customer (Tenant) model — TG1.AI 商业化多租户主体。

每个 Customer = 一个付费客户租户。所有业务资源（Account / Lead / KB /
SourceGroup / AIPersona / Campaign 等）都通过 customer_id 归属到某个客户。
旧数据 customer_id=NULL 归"系统所有"，仅 admin 视角可见。

订阅 / 配额字段是 Epic 1 的骨架，Epic 2（订阅与计费引擎）会填充逻辑：
- plan: starter / growth / pro（对应 $199 / $299 / $599）
- *_quota: 三档套餐对应的配额上限
- subscription_status / current_period_end: 由支付 webhook 维护
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# 订阅套餐（与 [[project-business-model-aas]] 三档对齐）
PLAN_STARTER = "starter"  # $199 / 3 acc / 500 grp
PLAN_GROWTH = "growth"    # $299 / 5 acc / 1000 grp
PLAN_PRO = "pro"          # $599 / 10 acc / 3000 grp
PLAN_CODES = {PLAN_STARTER, PLAN_GROWTH, PLAN_PRO}

# 套餐对应配额（Epic 2 计费时按这张表分配）
PLAN_QUOTA = {
    PLAN_STARTER: {"account": 3, "group": 500, "token": 2_000_000, "seat": 1, "replace_sla_h": 24},
    PLAN_GROWTH:  {"account": 5, "group": 1000, "token": 5_000_000, "seat": 3, "replace_sla_h": 12},
    PLAN_PRO:     {"account": 10, "group": 3000, "token": 15_000_000, "seat": 10, "replace_sla_h": 4},
}

# 套餐月费（USD）— 与 [[project-business-model-aas]] 三档对齐
PLAN_PRICE_USD = {
    PLAN_STARTER: 199.0,
    PLAN_GROWTH: 299.0,
    PLAN_PRO: 599.0,
}

# Customer 账户状态
STATUS_PENDING = "pending"      # 注册未付款
STATUS_ACTIVE = "active"        # 订阅生效中
STATUS_SUSPENDED = "suspended"  # 欠费暂停
STATUS_CANCELED = "canceled"    # 已取消
CUSTOMER_STATUSES = {STATUS_PENDING, STATUS_ACTIVE, STATUS_SUSPENDED, STATUS_CANCELED}


class CustomerBase(SQLModel):
    email: str = Field(unique=True, index=True, max_length=255)
    name: Optional[str] = Field(default=None, max_length=120)
    company: Optional[str] = Field(default=None, max_length=200)
    industry: Optional[str] = Field(default=None, index=True, max_length=80)

    status: str = Field(default=STATUS_PENDING, index=True, max_length=20)

    # 订阅（Epic 2 详化）
    plan: Optional[str] = Field(default=None, index=True, max_length=20)
    subscription_status: Optional[str] = Field(default=None, max_length=20)
    current_period_end: Optional[datetime] = None

    # 配额（Epic 2 计费时按 plan 写入；MVP 期手动设置）
    account_quota: int = Field(default=0)
    group_quota: int = Field(default=0)
    token_quota: int = Field(default=0)
    seat_quota: int = Field(default=1)

    # 已用量（计费/监控用，每次资源分配时递增）
    account_used: int = Field(default=0)
    group_used: int = Field(default=0)
    token_used: int = Field(default=0)
    seat_used: int = Field(default=0)  # Epic C1: customer_user 行数计数

    # Phase F1: 内部线索池标志。设为 true 的 Customer 不是付费客户，而是
    # 平台自营的「内部销售线索池」容器：拥有监听 TG 账号、关联监控规则，
    # 累积的 lead 只给 platform_sales 看。一个系统可有多个 internal pool
    # （比如按团队/地区拆）。
    is_internal_pool: bool = Field(default=False, index=True)


class Customer(CustomerBase, table=True):
    __tablename__ = "customer"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # ── Epic 5.0: 主号绑定 ──
    main_account_id: Optional[int] = Field(
        default=None, foreign_key="account.id", index=True,
    )

    # ── Epic 5.2: 业务对接群 + 主号接管超时 ──
    handover_group_link: Optional[str] = Field(default=None, max_length=256)
    takeover_timeout_minutes: int = Field(default=5)
    notify_main_account: bool = Field(default=True)


class CustomerCreate(SQLModel):
    email: str
    password: str
    name: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None


class CustomerLogin(SQLModel):
    email: str
    password: str


class CustomerRead(CustomerBase):
    """API 响应模型 — 不含 hashed_password。"""
    id: int
    created_at: datetime
    last_login_at: Optional[datetime] = None


class CustomerUpdate(SQLModel):
    """客户自助更新（不含敏感字段如 plan / quota，那些由计费系统改）。"""
    name: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
