"""ABExperimentAuditLog — 实验启停操作历史 (含自动停)

Records every state transition for an ABExperiment:
  'created' | 'started' | 'stopped' | 'auto_stopped'

operator_id is NULL for system-triggered events (e.g. auto_stopped).
reason carries the auto-stop trigger: 'significant_result' / 'max_duration' etc.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects import sqlite as _sqlite_dialect
from sqlmodel import Field, SQLModel

# SQLite requires INTEGER (not BIGINT) for auto-increment primary keys.
# On Postgres BigInteger maps to BIGINT (BIGSERIAL).
_BIG_PK = BigInteger().with_variant(_sqlite_dialect.INTEGER(), "sqlite")


class ABExperimentAuditLog(SQLModel, table=True):
    __tablename__ = "ab_experiment_audit_log"

    id: Optional[int] = Field(default=None, sa_column=Column(_BIG_PK, primary_key=True))
    experiment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("ab_experiments.id"), nullable=False)
    )
    action: str = Field(sa_column=Column(Text, nullable=False))
    operator_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, ForeignKey("user.id"), nullable=True)
    )
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: Optional[dict] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
