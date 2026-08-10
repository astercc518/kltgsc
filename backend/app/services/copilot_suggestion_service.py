"""
copilot_suggestion_service — compose 失败时, 把建议草稿落地供销售审。

流程:
  pending_reply.status='suggested' + reply_text=<suggested_text>
  + WebSocket broadcast 推 Inbox 前端
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)


def _update_pending_reply_status(pending_reply, suggested_text: str) -> None:
    with Session(engine) as session:
        obj = session.get(PendingReply, pending_reply.id)
        if obj is None:
            logger.warning("save_suggested: pending_reply %s not found", pending_reply.id)
            return
        obj.status = PendingReplyStatus.SUGGESTED.value
        obj.reply_text = suggested_text
        obj.responder_account_id = pending_reply.responder_account_id
        obj.decided_at = datetime.now(timezone.utc)
        session.add(obj)
        session.commit()


async def _broadcast_ws(payload: dict) -> None:
    try:
        from app.services.websocket_manager import manager as ws_manager  # 复用现有
        await ws_manager.broadcast(payload)
    except ImportError:
        logger.warning("ws_manager not available; suggestion saved but not broadcast")


async def save_suggested_reply(*, pending_reply, suggested_text: str) -> None:
    """主入口: 保存 suggested + 推 Inbox。任一失败只 warn, 不 raise。"""
    try:
        _update_pending_reply_status(pending_reply, suggested_text)
    except Exception:
        logger.exception("failed to persist suggested")
        return

    payload = {
        "type": "ai_suggestion_pending",
        "pending_reply_id": pending_reply.id,
        "customer_id": pending_reply.customer_id,
        "chat_id": pending_reply.chat_id,
        "source_user_id": pending_reply.source_user_id,
        "suggested_text": suggested_text,
    }
    try:
        await _broadcast_ws(payload)
    except Exception:
        logger.exception("ws broadcast failed; pending_reply already saved as suggested")
