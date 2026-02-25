"""
AI 人设模型
管理不同的 AI 角色配置
"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class AIPersonaBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    
    # 人设配置
    system_prompt: str  # 系统提示词
    tone: str = Field(default="friendly")  # friendly/professional/casual
    language: str = Field(default="zh")
    
    # 约束
    forbidden_topics: Optional[str] = None  # JSON 数组
    required_keywords: Optional[str] = None  # JSON 数组
    
    # 统计
    usage_count: int = Field(default=0)
    avg_reply_rate: Optional[float] = None


class AIPersona(AIPersonaBase, table=True):
    __tablename__ = "ai_persona"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AIPersonaCreate(SQLModel):
    name: str
    description: Optional[str] = None
    system_prompt: str
    tone: str = "friendly"
    language: str = "zh"
    forbidden_topics: Optional[str] = None
    required_keywords: Optional[str] = None


class AIPersonaUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tone: Optional[str] = None
    forbidden_topics: Optional[str] = None
    required_keywords: Optional[str] = None


class AIPersonaRead(AIPersonaBase):
    id: int
    created_at: datetime
