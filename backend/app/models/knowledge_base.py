"""
AI 知识库模型
用于 RAG (检索增强生成) 对话支持
"""
from typing import Optional, List
from sqlmodel import SQLModel, Field
from sqlalchemy import BigInteger, Column, Integer, String
from pgvector.sqlalchemy import Vector
from datetime import datetime


EMBEDDING_DIM = 768


class KnowledgeBaseBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None

    # 内容
    content: str  # 知识内容 (Markdown) — 对 QA 类型而言是 Q + A 的合成文本

    # 配置
    auto_update: bool = Field(default=False)
    source_url: Optional[str] = None  # 来源URL

    # ── 群组消息抽取来源（QA 类型）──
    source_type: str = Field(default="manual", index=True)  # manual, qa_extracted, scraped, file_import
    source_chat_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, index=True, nullable=True))
    source_chat_title: Optional[str] = None
    qa_question: Optional[str] = None
    qa_answer: Optional[str] = None
    qa_topic: Optional[str] = Field(default=None, index=True)
    qa_tags: Optional[str] = None  # JSON array string

    # ── 文档导入 / 分类元信息 ──
    category: Optional[str] = Field(default=None, sa_column=Column(String, index=True, nullable=True))
    language: Optional[str] = None
    parent_doc_id: Optional[str] = Field(default=None, sa_column=Column(String, index=True, nullable=True))
    chunk_index: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    source_filename: Optional[str] = None

    # ── 向量召回 ──
    embedding: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(Vector(EMBEDDING_DIM), nullable=True),
    )


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


class KnowledgeBaseRead(SQLModel):
    """API 响应模型 — 显式排除 embedding 字段，避免 768 维向量进入 JSON。"""
    id: int
    name: str
    description: Optional[str] = None
    content: str
    auto_update: bool = False
    source_url: Optional[str] = None
    source_type: str = "manual"
    source_chat_id: Optional[int] = None
    source_chat_title: Optional[str] = None
    qa_question: Optional[str] = None
    qa_answer: Optional[str] = None
    qa_topic: Optional[str] = None
    qa_tags: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    parent_doc_id: Optional[str] = None
    chunk_index: Optional[int] = None
    source_filename: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# 战役-知识库关联表
class CampaignKnowledgeLink(SQLModel, table=True):
    __tablename__ = "campaign_knowledge_link"
    
    campaign_id: int = Field(foreign_key="campaign.id", primary_key=True)
    knowledge_base_id: int = Field(foreign_key="ai_knowledge_base.id", primary_key=True)
