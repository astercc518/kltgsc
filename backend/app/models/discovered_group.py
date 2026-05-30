"""DiscoveredGroup — 待审批/已审批的候选线索群"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects import sqlite as _sqlite_dialect
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# BigInteger primary key: BIGINT on Postgres, INTEGER on SQLite (for test compat)
_BIG_PK = BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite")


class DiscoveredGroup(SQLModel, table=True):
    __tablename__ = "discovered_group"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(_BIG_PK, primary_key=True),
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    chat_username: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    chat_link: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    chat_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite"),
            nullable=True,
        ),
    )
    title: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    members_count: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    daily_messages: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    category: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str = Field(sa_column=Column(Text, nullable=False))
    source_query: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    status: str = Field(default="pending", sa_column=Column(Text, nullable=False))
    metadata_json: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True),
    )
    discovered_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    decided_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    decided_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("customer_user.id"), nullable=True),
    )
