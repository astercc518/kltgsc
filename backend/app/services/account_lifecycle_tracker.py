"""
account_lifecycle_tracker — 账号生命周期事件记录 + 统计工具。

设计原则:
- record_event 绝不抛出异常（DB 写失败只 warn + 尝试 rollback）。
  可安全嵌入 listener / dispatcher 的异常处理块中。
- count_kicks_in_window 面向 Phase 5 Task 4 的健康度指标计算。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.models.account_lifecycle_event import AccountLifecycleEvent

logger = logging.getLogger(__name__)

# Event types recognised by count_kicks_in_window
_KICK_EVENT_TYPES = ("kicked_from_chat", "session_invalid", "banned")


def record_event(
    *,
    session: Session,
    account_id: int,
    event_type: str,
    chat_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Write one AccountLifecycleEvent row.

    Never raises — on any error, logs a warning and attempts rollback.
    The caller's transaction is NOT impacted (the caller should use a
    separate short-lived session, identical to usage_tracker pattern).
    """
    try:
        now = datetime.now(tz=timezone.utc)
        event = AccountLifecycleEvent(
            account_id=account_id,
            event_type=event_type,
            chat_id=chat_id,
            reason=reason,
            metadata_json=metadata,
            created_at=now,
        )
        session.add(event)
        session.commit()
    except Exception as exc:
        logger.warning(
            "account_lifecycle_tracker.record_event failed "
            "(account_id=%s, event_type=%s): %s",
            account_id,
            event_type,
            exc,
        )
        try:
            session.rollback()
        except Exception:
            pass


def count_kicks_in_window(
    *,
    session: Session,
    account_ids: List[int],
    window_hours: int = 48,
) -> int:
    """
    Count kick-style events for a set of accounts within the last *window_hours*.

    Counted event_types: 'kicked_from_chat', 'session_invalid', 'banned'.

    Returns 0 when *account_ids* is empty.
    """
    if not account_ids:
        return 0

    since = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)

    stmt = (
        select(func.count(AccountLifecycleEvent.id))
        .where(AccountLifecycleEvent.account_id.in_(account_ids))  # type: ignore[union-attr]
        .where(AccountLifecycleEvent.event_type.in_(_KICK_EVENT_TYPES))  # type: ignore[union-attr]
        .where(AccountLifecycleEvent.created_at >= since)
    )
    result = session.exec(stmt).one()
    return result or 0
