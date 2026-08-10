"""
PendingReply — 群内 AI 销售员管线的状态机表。

每条群消息命中 LeadDetector 后入一行, Celery beat 按 fire_at 扫描推进:
observing -> risk_check -> composing -> sent (或 skipped_*/failed/suggested)

Spec: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §4.2
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class PendingReplyStatus(str, Enum):
    """全部 11 个状态 (spec §4.2)"""
    OBSERVING = "observing"
    RISK_CHECK = "risk_check"
    COMPOSING = "composing"
    SENT = "sent"
    SKIPPED_HUMAN_REPLIED = "skipped_human_replied"
    SKIPPED_THROTTLED = "skipped_throttled"
    SKIPPED_DUP = "skipped_dup"
    SKIPPED_BORDERLINE = "skipped_borderline"
    SKIPPED_NO_ACCOUNT = "skipped_no_account"
    FAILED = "failed"
    SUGGESTED = "suggested"


class PendingReply(SQLModel, table=True):
    __tablename__ = "pending_replies"

    # --- identifiers ---
    id: Optional[int] = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True)
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    monitor_id: int = Field(
        sa_column=Column(Integer, ForeignKey("keywordmonitor.id"), nullable=False)
    )
    responder_account_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("account.id"), nullable=True),
    )

    # --- source identifiers ---
    chat_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    message_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_user_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_text: str = Field(sa_column=Column(Text, nullable=False))

    # --- layer fields ---
    layer1_matched: Optional[dict] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    layer2_similarity: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    layer3_score: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    layer3_needs: Optional[list] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    layer3_solution_topic: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    layer3_confidence: Optional[float] = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )

    # --- status / timestamps ---
    status: str = Field(sa_column=Column(Text, nullable=False))
    fire_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    decided_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    sent_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    skip_reason: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    # --- reply / output fields ---
    reply_text: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    lead_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("lead.id"), nullable=True),
    )
    experiment_tag: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
