"""
group_reply_context_service — 查 (customer, source_user) 7 天内
status=sent 的群回复历史, 喂给 ai_reply_service 拼私聊 prompt。

参考 spec §2.3 + §8.1 集成点 2
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlmodel import select

from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

GROUP_CONTEXT_WINDOW_DAYS = 7


def fetch_recent_group_replies_for_user(
    *, session, customer_id: int, source_user_id: int, limit: int = 3,
) -> list[dict]:
    """
    返回近期群内对此 user 的回复历史 (用于私聊 LLM 拼 prompt).

    Returns:
        [{"reply_text": str, "extracted_needs": [str],
          "solution_topic": str, "sent_at": datetime, "chat_id": int}, ...]
        最多 limit 条, 按 sent_at desc。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=GROUP_CONTEXT_WINDOW_DAYS)
    stmt = (
        select(PendingReply).where(
            PendingReply.customer_id == customer_id,
            PendingReply.source_user_id == source_user_id,
            PendingReply.status == PendingReplyStatus.SENT.value,
            PendingReply.sent_at >= cutoff,
        )
        .order_by(PendingReply.sent_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(stmt).all())
    return [
        {
            "reply_text": r.reply_text or "",
            "extracted_needs": list(r.layer3_needs or []),
            "solution_topic": r.layer3_solution_topic or "",
            "sent_at": r.sent_at,
            "chat_id": r.chat_id,
        }
        for r in rows
    ]
