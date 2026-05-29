"""
chitchat_dispatch — typing delay → Telethon 发群 → 写 chitchat_log。

复用 group_dispatcher 的 _telethon_send_to_group, 但走独立 log。
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlmodel import Session

from app.core.db import engine
from app.models.chitchat import ChitchatLog

logger = logging.getLogger(__name__)


async def dispatch_chitchat(
    *, account_id: int, chat_id: int, topic_id: int,
    text: str, typing_delay: int,
) -> bool:
    if not text:
        return False
    await asyncio.sleep(typing_delay)
    sent_ok = await _telethon_send_chitchat(
        account_id=account_id, chat_id=chat_id, text=text,
    )
    if not sent_ok:
        logger.warning("chitchat send failed account=%s chat=%s", account_id, chat_id)
        return False
    _insert_chitchat_log_row(
        account_id=account_id, chat_id=chat_id, topic_id=topic_id, text=text,
    )
    return True


async def _telethon_send_chitchat(*, account_id: int, chat_id: int, text: str) -> bool:
    """复用 group_dispatcher 的 telethon send (它已经处理了 account ORM fetch)。"""
    from app.services.group_dispatcher import _telethon_send_to_group
    try:
        return await _telethon_send_to_group(
            account_id=account_id, chat_id=chat_id, text=text,
        )
    except Exception:
        logger.exception("chitchat telethon send error")
        return False


def _insert_chitchat_log_row(*, account_id, chat_id, topic_id, text):
    """写 chitchat_log 行 (Phase 1 表已经建好)。"""
    with Session(engine) as session:
        log = ChitchatLog(
            account_id=account_id, chat_id=chat_id,
            topic_id=topic_id, sent_text=text,
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None),  # spec §4.2: TIMESTAMP no TZ
        )
        session.add(log)
        try:
            session.commit()
        except Exception:
            # UNIQUE (account, topic, chat, sent_at::date) 冲突容忍
            logger.warning("chitchat_log unique violation, skipping (idempotent)")
            session.rollback()
