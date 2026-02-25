"""
AI 知识库模型
用于 RAG (检索增强生成) 对话支持
"""
from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime


class KnowledgeBaseBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    
    # 内容
    content: str  # 知识内容 (Markdown)
    
    # 配置
    auto_update: bool = Field(default=False)
    source_url: Optional[str] = None  # 来源URL


class KnowledgeBase(KnowledgeBaseBase, table=True):
    __tablename__ = "ai_knowledge_base"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeBaseCreate(SQLModel):
    name: str
    description: Optional[str] = None
    content: str
    auto_update: bool = False
    source_url: Optional[str] = None


class KnowledgeBaseUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    auto_update: Optional[bool] = None
    source_url: Optional[str] = None


class KnowledgeBaseRead(KnowledgeBaseBase):
    id: int
    created_at: datetime
    updated_at: datetime


# 战役-知识库关联表
class CampaignKnowledgeLink(SQLModel, table=True):
    __tablename__ = "campaign_knowledge_link"
    
    campaign_id: int = Field(foreign_key="campaign.id", primary_key=True)
    knowledge_base_id: int = Field(foreign_key="ai_knowledge_base.id", primary_key=True)
