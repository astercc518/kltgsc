"""CaptchaEvent — 单次 CAPTCHA 事件 (handler/result)"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects import sqlite as _sqlite_dialect
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# BigInteger primary key: BIGINT on Postgres, INTEGER on SQLite (for test compat)
_BIG_PK = BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite")

# Handler name constants
HANDLER_INLINE_BUTTON = "inline_button"
HANDLER_TEXT_QA = "text_qa"
HANDLER_VISION = "vision"
HANDLER_ADMIN_DM = "admin_dm"


class CaptchaEvent(SQLModel, table=True):
    __tablename__ = "captcha_event"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(_BIG_PK, primary_key=True),
    )
    join_attempt_id: int = Field(
        sa_column=Column(
            BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite"),
            ForeignKey("join_attempt.id"),
            nullable=False,
        )
    )
    handler: str = Field(sa_column=Column(Text, nullable=False))
    input_summary: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # e.g. "Click 'I am human' button" or "Q: 你怎么知道这群?"
    output_summary: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # e.g. "Clicked button" or "Answered: 朋友推荐"
    succeeded: bool = Field(sa_column=Column(Boolean, nullable=False))
    error_message: Optional[str] = Field(
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
