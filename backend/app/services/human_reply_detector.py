"""
human_reply_detector — 判断 source_message 之后 N 分钟内
群里是否有其他用户对该线索做出反应。

信号 (任一命中即 detected=True):
  1. reply_chain: 有人后续消息 reply_to_msg_id == source_message_id
  2. keyword_cooccur: 有人提到 solution_topic 拆词后的任一 token (长度>=2)

source_user_id 自己的发言不算 (排除自言自语)。
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select

from app.models.group_message import GroupMessage

logger = logging.getLogger(__name__)


def _tokenize_topic(topic: str) -> list[str]:
    """简单拆词 (空格/中文标点), 过滤长度<2 的 token。"""
    if not topic:
        return []
    import re
    raw = re.split(r"[\s,，、。.!?！？/\-]+", topic.strip())
    return [t for t in raw if len(t) >= 2]


def has_human_or_other_account_replied(
    *,
    session, customer_id: int, chat_id: int,
    source_message_id: int, source_user_id: int,
    solution_topic: Optional[str],
    since: datetime, window_minutes: int = 5,
) -> dict:
    """
    Returns:
      {"detected": bool, "reason": "reply_chain" | "keyword_cooccur" | None,
       "matched_message_id": int | None}
    """
    until = since + timedelta(minutes=window_minutes)
    stmt = (
        select(GroupMessage)
        .where(
            GroupMessage.chat_id == chat_id,
            GroupMessage.customer_id == customer_id,
            GroupMessage.message_date >= since,
            GroupMessage.message_date <= until,
            GroupMessage.message_id != source_message_id,
        )
        .order_by(GroupMessage.message_date.asc())
        .limit(200)
    )
    rows = list(session.exec(stmt).all())

    tokens = _tokenize_topic(solution_topic or "")

    for msg in rows:
        if msg.sender_id == source_user_id:
            continue  # 自言自语不算

        # 信号 1: reply chain
        if getattr(msg, "reply_to_msg_id", None) == source_message_id:
            return {
                "detected": True, "reason": "reply_chain",
                "matched_message_id": msg.message_id,
            }

        # 信号 2: solution_topic 关键词共现
        if tokens:
            content_lower = (msg.content or "").lower()
            for tok in tokens:
                if tok.lower() in content_lower:
                    return {
                        "detected": True, "reason": "keyword_cooccur",
                        "matched_message_id": msg.message_id,
                    }

    return {"detected": False, "reason": None, "matched_message_id": None}
