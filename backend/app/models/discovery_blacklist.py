"""DiscoveryBlacklist — 客户拒绝过的群, 不再推荐"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects import sqlite as _sqlite_dialect
from sqlmodel import Field, SQLModel

# BigInteger primary key: BIGINT on Postgres, INTEGER on SQLite (for test compat)
_BIG_PK = BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite")


class DiscoveryBlacklist(SQLModel, table=True):
    __tablename__ = "discovery_blacklist"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(_BIG_PK, primary_key=True),
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )
    chat_link: str = Field(sa_column=Column(Text, nullable=False))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
