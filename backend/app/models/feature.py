"""
Feature Pack — Phase 2 of TG1.AI 计费体系

- FeatureRegistry: 全局功能注册表（系统级，含默认单价）
- CustomerFeature: 每客户功能权限 + 单价覆盖（仅在 admin 配置时存在行）

参考 docs/planning/bulk_send_spec.md + plan groovy-strolling-canyon.md
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ── Billing units (功能的计费单位) ─────────────────────────────────────
BILLING_UNIT_MESSAGE = "message"      # 群发消息 / 自动回复
BILLING_UNIT_MEMBER = "member"        # 采集成员
BILLING_UNIT_INVITE = "invite"        # 拉人入群
BILLING_UNIT_ACCOUNT = "account"      # 注册账号
BILLING_UNIT_QA_WINDOW = "qa_window"  # Q&A 抽取窗口
BILLING_UNIT_MB = "mb"                # KB 文件 MB
BILLING_UNIT_AI_REPLY = "ai_reply"    # AI 生成回复

BILLING_UNITS = {
    BILLING_UNIT_MESSAGE, BILLING_UNIT_MEMBER, BILLING_UNIT_INVITE,
    BILLING_UNIT_ACCOUNT, BILLING_UNIT_QA_WINDOW, BILLING_UNIT_MB,
    BILLING_UNIT_AI_REPLY,
}

# ── Categories (UI 分组用) ─────────────────────────────────────────────
CATEGORY_MARKETING = "marketing"
CATEGORY_SCRAPING = "scraping"
CATEGORY_AI = "ai"
CATEGORY_KB = "kb"
CATEGORY_ACCOUNT = "account"

CATEGORIES = {
    CATEGORY_MARKETING, CATEGORY_SCRAPING, CATEGORY_AI,
    CATEGORY_KB, CATEGORY_ACCOUNT,
}


# ── Models ─────────────────────────────────────────────────────────────


class FeatureRegistry(SQLModel, table=True):
    """全局功能定义表。由 alembic seed + admin UI 维护。"""
    __tablename__ = "feature_registry"

    slug: str = Field(primary_key=True, max_length=64)
    name_zh: str = Field(max_length=100)
    name_en: str = Field(max_length=100)
    description: str = Field(default="", max_length=500)

    billing_unit: str = Field(max_length=40, index=True)  # BILLING_UNIT_*
    default_price_cents: int = Field(ge=0)
    enabled_by_default: bool = Field(default=False, index=True)
    category: str = Field(max_length=40, index=True)  # CATEGORY_*
    is_active: bool = Field(default=True, index=True)  # 软下架

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerFeature(SQLModel, table=True):
    """单个客户的功能权限/单价覆盖。
    没有行 = 走 FeatureRegistry.enabled_by_default 默认。
    有行且 enabled=true = 强制开通；enabled=false = 强制禁用。
    """
    __tablename__ = "customer_feature"
    __table_args__ = (
        {"sqlite_autoincrement": True},  # 兼容 SQLite 测试环境
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    feature_slug: str = Field(
        foreign_key="feature_registry.slug", max_length=64, index=True
    )

    enabled: bool = Field(default=True)
    custom_price_cents: Optional[int] = Field(default=None, ge=0)
    # NULL = 用 registry 默认价；设了就用这个

    notes: str = Field(default="", max_length=500)
    granted_by_user_id: Optional[int] = Field(
        default=None, foreign_key="user.id"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Public read/write schemas ──────────────────────────────────────────


class FeatureRegistryRead(SQLModel):
    slug: str
    name_zh: str
    name_en: str
    description: str
    billing_unit: str
    default_price_cents: int
    enabled_by_default: bool
    category: str
    is_active: bool


class FeatureRegistryUpdate(SQLModel):
    """admin 改全局默认价 / enabled_by_default / is_active"""
    default_price_cents: Optional[int] = Field(default=None, ge=0)
    enabled_by_default: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = Field(default=None, max_length=500)


class CustomerFeatureRead(SQLModel):
    """客户视角：返回该 slug 的实际可用状态 + 当前单价（解析后）"""
    feature_slug: str
    enabled: bool
    unit_price_cents: int   # 解析后实际价格 (custom 或 default)
    is_custom_price: bool   # 是否走的自定义覆盖
    billing_unit: str
    name_zh: str
    name_en: str
    category: str
    notes: str = ""


class CustomerFeatureUpdate(SQLModel):
    """admin 设置某客户某功能"""
    enabled: bool = True
    custom_price_cents: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=500)


class FeatureUsageSummary(SQLModel):
    """按 feature 聚合的本月用量+花费（来自 wallet_transaction）"""
    feature_slug: str
    name_zh: str
    units_consumed: int
    total_charged_cents: int
    last_charged_at: Optional[datetime] = None


class EstimateCostRequest(SQLModel):
    units: int = Field(ge=1)


class EstimateCostResponse(SQLModel):
    feature_slug: str
    units: int
    unit_price_cents: int
    total_cost_cents: int
    can_afford: bool
    balance_cents: int
