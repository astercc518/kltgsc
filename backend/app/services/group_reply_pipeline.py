"""
group_reply_pipeline — 群内 AI 销售员管线入口。

每条群消息从 listener_service._handle_message 调一次本入口。
本模块只做编排：早返 → Layer 1 → 入 pending_replies。Layer 2/3 在 Phase 2 加。

Phase 1 流程:
  msg → entrypoint(msg, account, monitor) →
    (skip collector / no_customer / feature_off / monitor_no_customer / empty_text) →
    layer1_keyword_match → (skip if miss) →
    INSERT pending_replies(status='observing', fire_at=now+random(60..900))

参考: spec §2.1, §3.1
"""
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.group_reply_config import (
    DEFAULT_PERSONA, GROUP_AI_REPLY_ENABLED,
)
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.lead_detector import layer1_keyword_match

logger = logging.getLogger(__name__)


async def entrypoint(msg, account, monitor) -> dict:
    """
    Args:
        msg: Telethon Message object (须含 text, chat_id, id, sender_id)
        account: app.models.account.Account (含 customer_id, role)
        monitor: KeywordMonitor (含 keyword_filters, keyword)

    Returns:
        {"skipped": <reason>} 或 {"pending_reply_id": <id>}
    """
    # Guard: feature flag
    if not GROUP_AI_REPLY_ENABLED:
        return {"skipped": "feature_off"}

    # Guard: collector accounts are observers only — never reply
    if getattr(account, "role", None) == "collector":
        return {"skipped": "collector_role"}

    # Guard: account must be associated with a customer
    customer_id = getattr(account, "customer_id", None)
    if customer_id is None:
        return {"skipped": "no_customer"}

    # Guard: monitor must have a customer
    if getattr(monitor, "customer_id", None) is None:
        return {"skipped": "monitor_no_customer"}

    # Guard: message must have text
    text = getattr(msg, "text", None) or ""
    if not text:
        return {"skipped": "empty_text"}

    # Layer 1: keyword filter
    layer1 = layer1_keyword_match(
        text,
        filters=getattr(monitor, "keyword_filters", None),
        legacy_keyword=getattr(monitor, "keyword", None),
    )
    if not layer1["pass"]:
        return {"skipped": "layer1_miss"}

    # Pick a random observation window in [obs_min, obs_max]
    obs_min, obs_max = DEFAULT_PERSONA["observation_window_seconds_range"]
    obs_seconds = random.randint(obs_min, obs_max)

    pr = _insert_pending_reply(
        customer_id=customer_id,
        monitor_id=monitor.id,
        chat_id=msg.chat_id,
        message_id=msg.id,
        source_user_id=msg.sender_id,
        source_text=text,
        layer1_matched={"matched": layer1["matched"]},
        observation_window_seconds=obs_seconds,
    )
    logger.info(
        "group_reply_pipeline: pending_reply id=%s queued (window=%ss)",
        pr.id, obs_seconds,
    )
    return {"pending_reply_id": pr.id}


def _insert_pending_reply(
    *,
    customer_id: int,
    monitor_id: int,
    chat_id: int,
    message_id: int,
    source_user_id: int,
    source_text: str,
    layer1_matched: dict,
    observation_window_seconds: int,
) -> PendingReply:
    """Sync insert using the project's standard sync SQLModel Session pattern.

    Mirrors the pattern used throughout backend/app/services/ (e.g. billing_service.py,
    ai_reply_service.py) which all use sync `Session(engine)` from app.core.db.
    """
    from sqlmodel import Session
    from app.core.db import engine

    now = datetime.now(timezone.utc)
    pr = PendingReply(
        customer_id=customer_id,
        monitor_id=monitor_id,
        chat_id=chat_id,
        message_id=message_id,
        source_user_id=source_user_id,
        source_text=source_text,
        layer1_matched=layer1_matched,
        status=PendingReplyStatus.OBSERVING.value,
        fire_at=now + timedelta(seconds=observation_window_seconds),
        created_at=now,
    )
    with Session(engine) as session:
        session.add(pr)
        session.commit()
        session.refresh(pr)
    return pr
