"""AccountLifecycleEvent — 账号状态变化事件 (踢号 / session 失效 / banned 等)"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class AccountLifecycleEvent(SQLModel, table=True):
    __tablename__ = "account_lifecycle_events"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    account_id: int = Field(
        sa_column=Column(Integer, ForeignKey("account.id"), nullable=False)
    )
    event_type: str = Field(sa_column=Column(Text, nullable=False))
    chat_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False),
    )
