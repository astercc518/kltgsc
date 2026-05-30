"""
lead_conversion_service — 查 source_user 在群回复后 N 小时内是否私聊转化为 Lead。

Lead 表字段（由 lead.py 摸底确认）:
  - Lead.telegram_user_id: int  — source TG 用户 ID
  - Lead.customer_id: int       — 归属租户
  - Lead.created_at: datetime   — Lead 创建时间

PendingReply 表字段（由 pending_reply.py 摸底确认）:
  - PendingReply.source_user_id: int  — 触发群消息的 TG 用户 ID
  - PendingReply.customer_id: int     — 归属租户（用于跨租户隔离）
  - PendingReply.sent_at: datetime    — 实际发送时间
  - PendingReply.experiment_tag: str  — A/B 实验标签
  - PendingReply.status: str          — 状态（"sent" 为已发送）
"""
import logging
from datetime import timedelta

from sqlalchemy import and_, exists
from sqlmodel import select, func

from app.models.lead import Lead
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

PRIVATE_CONVERSION_WINDOW_HOURS = 24


def count_private_conversions_for_experiment(
    *,
    session,
    experiment_tag: str,
    window_hours: int = PRIVATE_CONVERSION_WINDOW_HOURS,
) -> int:
    """Single JOIN-based query, prevents O(N) round-trips.

    Counts distinct sent PendingReply rows where a Lead for the same
    (telegram_user_id, customer_id) was created within
    [sent_at, sent_at + window_hours].

    Cross-tenant isolation: Lead is filtered by PendingReply.customer_id so
    that TG user 99999 DMing Customer B after receiving Customer A's experiment
    reply does NOT count as a Customer A conversion.

    Algorithm:
      Single EXISTS subquery — for each qualifying PendingReply row check
      whether a matching Lead row exists within the attribution window.
      This replaces the previous O(N) per-row Lead count loop.

    Args:
        session: SQLModel/SQLAlchemy session (supports .exec()).
        experiment_tag: A/B experiment tag to filter PendingReply rows.
        window_hours: Attribution window in hours after sent_at (default 24).

    Returns:
        int: Number of private conversion events.
    """
    # EXISTS subquery: does a matching Lead row exist for this PendingReply?
    lead_exists_subq = (
        select(Lead.id)
        .where(
            and_(
                Lead.telegram_user_id == PendingReply.source_user_id,
                Lead.customer_id == PendingReply.customer_id,  # tenant isolation
                Lead.created_at >= PendingReply.sent_at,
                Lead.created_at
                <= PendingReply.sent_at + timedelta(hours=window_hours),
            )
        )
        .exists()
    )

    stmt = select(func.count(PendingReply.id)).where(
        PendingReply.experiment_tag == experiment_tag,
        PendingReply.status == PendingReplyStatus.SENT.value,
        PendingReply.sent_at.isnot(None),  # type: ignore[union-attr]
        lead_exists_subq,
    )

    result = int(session.exec(stmt).first() or 0)

    logger.debug(
        "lead_conversion: experiment_tag=%s conversions=%d window_hours=%d",
        experiment_tag,
        result,
        window_hours,
    )
    return result
