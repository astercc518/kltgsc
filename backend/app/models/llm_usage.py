"""
LLMUsage — 单次 LLM/Embedding 调用的 token & 成本记录。

数据用于 AIPage "费用" Tab 的本地估算。写入失败只 warning，不阻塞主流程。
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LLMUsage(SQLModel, table=True):
    __tablename__ = "llm_usage"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)

    provider: str = Field(index=True)
    model: str = Field(index=True)
    source: str = Field(index=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    account_id: Optional[int] = Field(default=None, index=True)
    persona_id: Optional[int] = Field(default=None, index=True)
    chat_id: Optional[str] = Field(default=None, index=True)
    moderation_score: Optional[float] = Field(default=None)
    block_layer: Optional[str] = Field(default=None, max_length=8)  # "L0" | "L1" | "L2" | None
    routed_provider: Optional[str] = Field(default=None, max_length=32)
