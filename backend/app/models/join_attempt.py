"""JoinAttempt — 加群尝试状态机"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects import sqlite as _sqlite_dialect
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# BigInteger primary key: BIGINT on Postgres, INTEGER on SQLite (for test compat)
_BIG_PK = BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite")

# Status constants
STATUS_PENDING = "pending"
STATUS_JOINING = "joining"
STATUS_CAPTCHA = "captcha"
STATUS_JOINED = "joined"
STATUS_FAILED = "failed"
STATUS_ABANDONED = "abandoned"

# Captcha type constants
CAPTCHA_INLINE_BUTTON = "inline_button"
CAPTCHA_TEXT_QA = "text_qa"
CAPTCHA_VISION = "vision"
CAPTCHA_ADMIN_DM = "admin_dm"
CAPTCHA_UNKNOWN = "unknown"


class JoinAttempt(SQLModel, table=True):
    __tablename__ = "join_attempt"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(_BIG_PK, primary_key=True),
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    account_id: int = Field(
        sa_column=Column(Integer, ForeignKey("account.id"), nullable=False)
    )
    discovered_group_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite"),
            ForeignKey("discovered_group.id"),
            nullable=True,
        ),
    )
    chat_link: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(
        default=STATUS_PENDING,
        sa_column=Column(Text, nullable=False),
    )
    captcha_type: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    captcha_attempts: int = Field(
        default=0, sa_column=Column(Integer, nullable=False)
    )
    last_error: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    metadata_json: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
