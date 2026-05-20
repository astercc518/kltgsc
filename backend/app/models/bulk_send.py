"""
TG Bulk Send — W2 data models

- BulkBatch: 一个发送任务（一个客户，一段时间，发给一批目标）
- BulkTarget: 批次内的单个目标号（CSV 解析后产物，全平台按 customer×tg_user_id 去重）
- BulkTemplateVariant: 同 batch 多个文案变体，发送时按权重随机选

参考 docs/planning/bulk_send_spec.md §3.1
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


# ── BulkBatch status ────────────────────────────────────────────────────
BATCH_DRAFT = "draft"
BATCH_PENDING = "pending"
BATCH_RUNNING = "running"
BATCH_PAUSED = "paused"
BATCH_COMPLETED = "completed"
BATCH_FAILED = "failed"
BATCH_CANCELED = "canceled"

BATCH_STATUSES = {
    BATCH_DRAFT, BATCH_PENDING, BATCH_RUNNING, BATCH_PAUSED,
    BATCH_COMPLETED, BATCH_FAILED, BATCH_CANCELED,
}

# ── BulkTarget status ───────────────────────────────────────────────────
TARGET_PENDING = "pending"
TARGET_SENDING = "sending"
TARGET_SENT = "sent"
TARGET_DELIVERED = "delivered"
TARGET_FAILED = "failed"
TARGET_REPLIED = "replied"
TARGET_OPTED_OUT = "opted_out"
TARGET_SKIPPED = "skipped"  # dedup / opt-out / invalid

TARGET_STATUSES = {
    TARGET_PENDING, TARGET_SENDING, TARGET_SENT, TARGET_DELIVERED,
    TARGET_FAILED, TARGET_REPLIED, TARGET_OPTED_OUT, TARGET_SKIPPED,
}


# ── Tables ─────────────────────────────────────────────────────────────


class BulkBatch(SQLModel, table=True):
    __tablename__ = "bulk_batch"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)

    name: str = Field(max_length=120)
    message_template: str  # backward-compat: primary content if no variants

    status: str = Field(default=BATCH_DRAFT, max_length=20, index=True)

    total_targets: int = Field(default=0)
    sent_count: int = Field(default=0)
    delivered_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    replied_count: int = Field(default=0)
    skipped_count: int = Field(default=0)

    # 创建时按当前 tier 估算的单价，便于事后审计（实际扣款仍按发送时 tier 算）
    estimated_unit_price_cents: int = Field(default=15)
    estimated_total_cents: int = Field(default=0)

    # 发送节流
    min_delay_sec: int = Field(default=30)
    max_delay_sec: int = Field(default=180)

    started_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    pause_reason: Optional[str] = Field(default=None, max_length=120)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BulkTarget(SQLModel, table=True):
    __tablename__ = "bulk_target"
    __table_args__ = (
        UniqueConstraint("customer_id", "tg_user_id", name="uq_bulk_target_customer_user"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="bulk_batch.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)

    # 至少要有 tg_user_id 或 tg_username 或 phone 之一
    tg_user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, index=True, nullable=True),
    )
    tg_username: Optional[str] = Field(default=None, max_length=64, index=True)
    phone: Optional[str] = Field(default=None, max_length=24, index=True)

    # CSV 里附带的字段（自由文本）
    display_name: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, max_length=4)  # ISO-3166 alpha-2
    extra_json: Optional[str] = None  # 整行 CSV 原文，保留扩展字段

    status: str = Field(default=TARGET_PENDING, max_length=20, index=True)
    assigned_account_id: Optional[int] = Field(
        default=None, foreign_key="account.id", index=True
    )

    sent_at: Optional[datetime] = None
    failed_reason: Optional[str] = Field(default=None, max_length=200)
    variant_id: Optional[int] = Field(default=None, foreign_key="bulk_template_variant.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)


class BulkTemplateVariant(SQLModel, table=True):
    __tablename__ = "bulk_template_variant"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="bulk_batch.id", index=True)

    content: str
    weight: int = Field(default=1, ge=1)
    use_count: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Read schemas (API output) ──────────────────────────────────────────


class BulkBatchRead(SQLModel):
    id: int
    customer_id: int
    name: str
    message_template: str
    status: str
    total_targets: int
    sent_count: int
    delivered_count: int
    failed_count: int
    replied_count: int
    skipped_count: int
    estimated_unit_price_cents: int
    estimated_total_cents: int
    min_delay_sec: int
    max_delay_sec: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    paused_at: Optional[datetime]
    pause_reason: Optional[str]
    created_at: datetime


class BulkTargetRead(SQLModel):
    id: int
    batch_id: int
    tg_user_id: Optional[int]
    tg_username: Optional[str]
    phone: Optional[str]
    display_name: Optional[str]
    country: Optional[str]
    status: str
    assigned_account_id: Optional[int]
    sent_at: Optional[datetime]
    failed_reason: Optional[str]
    created_at: datetime


class BulkTemplateVariantRead(SQLModel):
    id: int
    batch_id: int
    content: str
    weight: int
    use_count: int
    created_at: datetime


class BulkBatchDetail(BulkBatchRead):
    variants: list[BulkTemplateVariantRead] = []
    targets_preview: list[BulkTargetRead] = []  # 前 N 条便于客户校验


# ── Write schemas (API input) ──────────────────────────────────────────


class BulkBatchCreate(SQLModel):
    """Customer-facing create-batch payload.

    Either provide a flat csv_text (1 target per line, tg_username or phone),
    or a structured targets list. message_template is required; variants are
    optional but at least 5 are required before the batch can be started
    (enforced at /start, not here).
    """
    name: str = Field(min_length=1, max_length=120)
    message_template: str = Field(min_length=1, max_length=4000)
    csv_text: Optional[str] = None
    variants: list[str] = []
    min_delay_sec: int = Field(default=30, ge=10, le=600)
    max_delay_sec: int = Field(default=180, ge=30, le=1800)


class BulkCostPreviewRequest(SQLModel):
    """Compute estimated cost given a target count, without creating a batch."""
    target_count: int = Field(ge=1, le=500_000)
