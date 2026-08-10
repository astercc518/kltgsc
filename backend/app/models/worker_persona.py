"""WorkerPersona — worker 账号的"真人画像"配置（Phase 3 启用读取）。

NOTE: 与 ai_persona.py 中的 AIPersona 是不同概念。
AIPersona  = LLM system_prompt 模板（"金牌销售"/"技术分析师"）。
WorkerPersona = 单个 TG 账号的拟真身份（地区/职业/口头禅/活跃时段）。

Phase 1: 表已建好，管线使用 group_reply_config.DEFAULT_PERSONA 兜底。
Phase 3: 加载真实 WorkerPersona 替换兜底。

Spec: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §4.3
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlmodel import Field, SQLModel


_DEFAULT_ACTIVE_HOURS = {
    "mon": [[9, 18]], "tue": [[9, 18]], "wed": [[9, 18]],
    "thu": [[9, 18]], "fri": [[9, 18]], "sat": [], "sun": [],
}


class WorkerPersona(SQLModel, table=True):
    __tablename__ = "worker_personas"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))

    account_id: int = Field(
        sa_column=Column(Integer, ForeignKey("account.id"), unique=True, nullable=False)
    )
    customer_id: int = Field(
        sa_column=Column(Integer, ForeignKey("customer.id"), nullable=False)
    )

    # --- identity fields ---
    display_name: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    age_range: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    region: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    occupation: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    speaking_style: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    catchphrases: list = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    active_hours: dict = Field(
        default_factory=lambda: dict(_DEFAULT_ACTIVE_HOURS),
        sa_column=Column(JSON, nullable=False),
    )

    # --- quota / timing fields ---
    daily_reply_quota: int = Field(default=5, sa_column=Column(Integer, nullable=False))
    per_chat_daily_quota: int = Field(default=2, sa_column=Column(Integer, nullable=False))
    per_chat_cooldown_minutes: int = Field(default=120, sa_column=Column(Integer, nullable=False))
    daily_chitchat_quota: int = Field(default=7, sa_column=Column(Integer, nullable=False))

    observation_window_seconds_range: list = Field(
        default_factory=lambda: [60, 900], sa_column=Column(JSON, nullable=False)
    )
    typing_delay_seconds_range: list = Field(
        default_factory=lambda: [30, 120], sa_column=Column(JSON, nullable=False)
    )

    param_version: str = Field(default="v1", sa_column=Column(Text, nullable=False))

    # --- timestamps ---
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
