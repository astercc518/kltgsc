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
from typing import Any, Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

try:
    from pgvector.sqlalchemy import Vector as _PGVector
except ImportError:
    _PGVector = None


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

    # ── Phase 1: ICP 画像 + 潜在客户探测器参数 ──
    # icp_profile_text: LLM 生成的 ICP 自然语言描述（可空，首次激活后生成）
    icp_profile_text: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    # icp_profile_embedding: 768-dim pgvector embedding，供 cosine 相似度粗筛
    # pgvector 在生产环境必须存在；graceful import fallback 仅供本地无 pgvector 开发用
    icp_profile_embedding: Optional[Any] = Field(
        default=None,
        sa_column=Column(_PGVector(768), nullable=True) if _PGVector is not None else Column(Text, nullable=True),
    )

    # lead_detector_thresholds: 结构化阈值参数，Postgres 实列为 JSONB (migration)；
    # 此处用跨方言 JSON 类型，使 SQLite-based 单测 create_all 也能通过。
    lead_detector_thresholds: dict = Field(
        default_factory=lambda: {
            "layer2_sim": 0.55,
            "layer3_score": 60,
            "layer3_confidence": 0.7,
        },
        sa_column=Column(
            JSON,
            nullable=False,
            server_default='{"layer2_sim":0.55,"layer3_score":60,"layer3_confidence":0.7}',
        ),
    )

    # param_version: 参数版本标记，用于感知 threshold schema 迭代
    param_version: str = Field(
        default="v1",
        sa_column=Column(Text, nullable=False, server_default="v1"),
    )

    # ── Phase 10: captcha 自动答题 / admin DM 模板 ──
    # captcha_join_template: text_qa handler 用做答题上下文
    #   "你为什么想加这个群" / "怎么知道这个群"。建议 < 200 字。
    captcha_join_template: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # captcha_intro_template: admin_dm handler 用做申请加群话术
    #   eg "你好，看到xx推荐的，想加群学习交流"。建议 < 300 字。
    captcha_intro_template: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


class CustomerCreate(SQLModel):
    email: str
    password: str
    name: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    # Landing trial grant tag. Free-text, but only the literal "landing" is
    # honoured by register_customer to issue the $20 free credit. The amount
    # is server-side fixed (clients can't request more) — see
    # backend/app/api/v1/endpoints/auth.py register_customer.
    ref: Optional[str] = None


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
