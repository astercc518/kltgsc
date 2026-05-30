"""CaseStudy — 客户成交案例库（Phase 2 启用查询）。

Phase 1: 表已建好，ReplyComposer 不查询本表。
Phase 2: 加 embedding 相似度匹配逻辑。

Spec: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §4.3
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel

try:
    from pgvector.sqlalchemy import Vector as _PGVector
except ImportError:
    _PGVector = None


class CaseStudy(SQLModel, table=True):
    __tablename__ = "case_studies"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))

    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )

    # --- content fields ---
    industry: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    deal_size: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    period: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    problem: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    solution: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    outcome: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    tags: Optional[list] = Field(default=None, sa_column=Column(JSON, nullable=True))

    # embedding: pgvector(768) when available, else Text placeholder
    embedding: Optional[Any] = Field(
        default=None,
        sa_column=Column(_PGVector(768), nullable=True) if _PGVector is not None else Column(Text, nullable=True),
    )

    source: str = Field(sa_column=Column(Text, nullable=False))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))

    # --- timestamps ---
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_used_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
