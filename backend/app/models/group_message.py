"""
群组/私聊消息历史 - 用于知识库采集和后续 RAG
独立于 ChatHistory（ChatHistory 用于 actor↔lead 私聊行为日志）
"""
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, UniqueConstraint
from sqlalchemy import BigInteger, Column, ForeignKey


class GroupMessageBase(SQLModel):
    account_id: int = Field(index=True, foreign_key="account.id")
    chat_id: int = Field(sa_column=Column(BigInteger, index=True, nullable=False))
    chat_title: Optional[str] = None
    chat_type: str = Field(default="supergroup")  # supergroup, group, private, channel
    chat_username: Optional[str] = None

    message_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    sender_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, index=True, nullable=True))
    sender_username: Optional[str] = None
    sender_name: Optional[str] = None

    content: str  # text or caption
    reply_to_msg_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    has_media: bool = Field(default=False)
    media_type: Optional[str] = None  # photo, video, document, voice, etc.

    message_date: datetime  # original Telegram timestamp
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    # 后续 Q&A 抽取标记
    qa_extracted: bool = Field(default=False, index=True)


class GroupMessage(GroupMessageBase, table=True):
    __tablename__ = "group_message"
    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "message_id", name="uq_group_msg"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)


class GroupMessageRead(GroupMessageBase):
    id: int
