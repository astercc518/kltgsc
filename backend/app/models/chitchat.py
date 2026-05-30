"""ChitchatPool / ChitchatLog — 闲聊话题库与发送记录（Phase 3 启用）。

ChitchatPool : 可复用的话题模板（全局或客户专属）。
ChitchatLog  : 每次实际发送的记录，带 unique 约束防同日重复。

Phase 1: 表已建好，ChitchatScheduler 未实装（DEFAULT_PERSONA.daily_chitchat_quota=0）。
Phase 3: 实装 ChitchatScheduler + 填充 chitchat_pool 数据。

Spec: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §4.3
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class ChitchatPool(SQLModel, table=True):
    __tablename__ = "chitchat_pool"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))

    customer_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=True),
    )

    topic_category: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    prompt_template: str = Field(sa_column=Column(Text, nullable=False))
    tags: Optional[list] = Field(default=None, sa_column=Column(JSON, nullable=True))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ChitchatLog(SQLModel, table=True):
    __tablename__ = "chitchat_log"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))

    account_id: int = Field(
        sa_column=Column(Integer, ForeignKey("account.id"), nullable=False)
    )
    chat_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    topic_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("chitchat_pool.id"), nullable=True),
    )
    sent_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    sent_at: Optional[datetime] = Field(
        default=None,
        # timezone=False → TIMESTAMP WITHOUT TIME ZONE, matching the Phase 1 migration.
        # Required for the IMMUTABLE expression index: (sent_at::date).
        sa_column=Column(DateTime(timezone=False), nullable=False),
    )
