"""ABExperiment — A/B 实验定义（Phase 5 启用）。

每行代表一个实验配置，variants JSONB 存权重分配：
  [{"tag": "ctrl", "weight": 0.5}, {"tag": "v1", "weight": 0.5}]

Phase 1: 表已建好，GroupDispatcher 的 experiment_tag 字段留空。
Phase 5: 实装 ABRouter，按 scope/scope_value 路由流量到不同 variant。

Spec: docs/superpowers/specs/2026-05-28-group-ai-sales-presence-design.md §4.3
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, JSON, Text
from sqlmodel import Field, SQLModel


class ABExperiment(SQLModel, table=True):
    __tablename__ = "ab_experiments"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True))

    name: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # scope: "global" | "customer" | "monitor"
    scope: str = Field(sa_column=Column(Text, nullable=False))
    scope_value: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # variants: [{"tag": str, "weight": float}, ...]
    variants: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))

    # status: "draft" | "running" | "paused" | "ended"
    status: str = Field(default="draft", sa_column=Column(Text, nullable=False))
    primary_metric: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # --- timestamps ---
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    ended_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
