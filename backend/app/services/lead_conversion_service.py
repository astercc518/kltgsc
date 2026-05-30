"""
lead_conversion_service — 查 source_user 在群回复后 N 小时内是否私聊转化为 Lead。

Lead 表字段（由 lead.py 摸底确认）:
  - Lead.telegram_user_id: int  — source TG 用户 ID
  - Lead.created_at: datetime   — Lead 创建时间

PendingReply 表字段（由 pending_reply.py 摸底确认）:
  - PendingReply.source_user_id: int  — 触发群消息的 TG 用户 ID
  - PendingReply.sent_at: datetime    — 实际发送时间
  - PendingReply.experiment_tag: str  — A/B 实验标签
  - PendingReply.status: str          — 状态（"sent" 为已发送）
"""
import logging
from datetime import timedelta

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
    """
    Returns count of distinct sent pending_reply rows (keyed by source_user_id +
    sent_at) where a Lead row for that user was created within [sent_at,
    sent_at + window_hours].

    Algorithm:
      1. Fetch all sent rows for experiment_tag (source_user_id, sent_at).
      2. For each row, count Lead rows matching telegram_user_id == source_user_id
         AND created_at in [sent_at, sent_at + window_hours].
      3. Each sent row that has at least one matching Lead counts as 1 conversion.

    Args:
        session: SQLModel/SQLAlchemy session (supports .exec()).
        experiment_tag: A/B experiment tag to filter PendingReply rows.
        window_hours: Attribution window in hours after sent_at (default 24).

    Returns:
        int: Number of private conversion events.
    """
    # Step 1: fetch sent rows for this experiment_tag
    sent_stmt = select(PendingReply.source_user_id, PendingReply.sent_at).where(
        PendingReply.experiment_tag == experiment_tag,
        PendingReply.status == PendingReplyStatus.SENT.value,
        PendingReply.sent_at.isnot(None),  # type: ignore[union-attr]
    )
    sent_rows = session.exec(sent_stmt).all()

    if not sent_rows:
        logger.debug(
            "lead_conversion: no sent rows for experiment_tag=%s", experiment_tag
        )
        return 0

    conversion_count = 0
    for source_user_id, sent_at in sent_rows:
        cutoff = sent_at + timedelta(hours=window_hours)

        lead_count_stmt = select(func.count(Lead.id)).where(  # type: ignore[arg-type]
            Lead.telegram_user_id == source_user_id,
            Lead.created_at >= sent_at,
            Lead.created_at <= cutoff,
        )
        lead_cnt = int(session.exec(lead_count_stmt).first() or 0)
        if lead_cnt > 0:
            conversion_count += 1

    logger.debug(
        "lead_conversion: experiment_tag=%s sent=%d conversions=%d window_hours=%d",
        experiment_tag,
        len(sent_rows),
        conversion_count,
        window_hours,
    )
    return conversion_count
