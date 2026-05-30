"""
experiment_metrics_service — 按 experiment_tag 聚合 4 个核心 A/B 指标。

参考 spec §10.4:

  1. reply_rate             = sent / total_triggered
  2. private_conversion_rate= private_conversions / sent
  3. kick_rate              = kicks_after_sent / sent
  4. anti_hallucination_failure_rate = suggested / (sent + suggested)

total_triggered = sent + suggested + skipped_total + failed

Phase 5 simplification
  _count_private_conversions_after_sent returns 0 (placeholder).
  Real Lead join is deferred to a later phase.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import select, func

from app.models.account_lifecycle_event import AccountLifecycleEvent
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

# Event types that count as a "kick" for the responder account.
_KICK_EVENT_TYPES = ("kicked_from_chat", "session_invalid", "banned")

# Window after a reply is sent within which a kick counts against it.
_KICK_WINDOW_HOURS = 48


@dataclass
class MetricCounters:
    """Raw event counts for one experiment_tag bucket."""

    sent: int
    suggested: int
    skipped_total: int
    failed: int
    private_conversion_count: int
    kick_count: int

    # ------------------------------------------------------------------
    # Derived property
    # ------------------------------------------------------------------

    @property
    def total_triggered(self) -> int:
        return self.sent + self.suggested + self.skipped_total + self.failed

    # ------------------------------------------------------------------
    # 4 core metrics — all safe against division-by-zero
    # ------------------------------------------------------------------

    def reply_rate(self) -> float:
        """sent / total_triggered"""
        denom = self.total_triggered
        return self.sent / denom if denom else 0.0

    def private_conversion_rate(self) -> float:
        """private_conversions / sent"""
        return self.private_conversion_count / self.sent if self.sent else 0.0

    def kick_rate(self) -> float:
        """kicks_after_sent / sent"""
        return self.kick_count / self.sent if self.sent else 0.0

    def anti_hallucination_failure_rate(self) -> float:
        """suggested / (sent + suggested)"""
        denom = self.sent + self.suggested
        return self.suggested / denom if denom else 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_status(*, session, experiment_tag: str, status: str) -> int:
    """Count PendingReply rows matching experiment_tag + status."""
    stmt = (
        select(func.count(PendingReply.id))
        .where(
            PendingReply.experiment_tag == experiment_tag,
            PendingReply.status == status,
        )
    )
    result = session.exec(stmt).one()
    return result or 0


def _count_private_conversions_after_sent(
    *, session, experiment_tag: str
) -> int:
    """
    Count source_users who private-messaged the main account within 24 h
    after their group reply was sent.

    TODO (Phase 6): implement real Lead join once Lead.source_tg_id is indexed
    and a private_chat_started_at timestamp is available.

    Phase 5 simplification: return 0 as placeholder.
    """
    return 0  # noqa: placeholder


def _count_kicks_after_sent(*, session, experiment_tag: str) -> int:
    """
    Count PendingReply rows (status=sent, for this experiment_tag) where
    the responder_account had a kick/ban/invalidation event within 48 h
    after the reply was sent.

    Single-query implementation using a JOIN — O(1) queries regardless of
    how many sent rows exist (replaces the previous N+1 per-row loop).
    """
    from sqlalchemy import and_

    stmt = (
        select(func.count(func.distinct(PendingReply.id)))
        .select_from(PendingReply)
        .join(
            AccountLifecycleEvent,
            and_(
                AccountLifecycleEvent.account_id == PendingReply.responder_account_id,
                AccountLifecycleEvent.event_type.in_(list(_KICK_EVENT_TYPES)),
                AccountLifecycleEvent.created_at >= PendingReply.sent_at,
                AccountLifecycleEvent.created_at
                <= PendingReply.sent_at + timedelta(hours=_KICK_WINDOW_HOURS),
            ),
        )
        .where(
            PendingReply.experiment_tag == experiment_tag,
            PendingReply.status == PendingReplyStatus.SENT.value,
            PendingReply.responder_account_id.isnot(None),  # type: ignore[union-attr]
            PendingReply.sent_at.isnot(None),  # type: ignore[union-attr]
        )
    )
    return int(session.exec(stmt).first() or 0)


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

def aggregate_metrics_by_tag(
    *, session, experiment_tag: str
) -> MetricCounters:
    """
    Aggregate all 4 core metrics for a single experiment_tag.

    Returns a MetricCounters dataclass with raw counts and computed rates.
    """
    sent = _count_status(
        session=session, experiment_tag=experiment_tag, status="sent"
    )
    suggested = _count_status(
        session=session, experiment_tag=experiment_tag, status="suggested"
    )
    failed = _count_status(
        session=session, experiment_tag=experiment_tag, status="failed"
    )

    # Sum all skip sub-statuses into a single total.
    skip_statuses = [
        PendingReplyStatus.SKIPPED_HUMAN_REPLIED.value,
        PendingReplyStatus.SKIPPED_THROTTLED.value,
        PendingReplyStatus.SKIPPED_DUP.value,
        PendingReplyStatus.SKIPPED_BORDERLINE.value,
        PendingReplyStatus.SKIPPED_NO_ACCOUNT.value,
    ]
    skipped_total = sum(
        _count_status(
            session=session, experiment_tag=experiment_tag, status=s
        )
        for s in skip_statuses
    )

    private_conversion_count = _count_private_conversions_after_sent(
        session=session, experiment_tag=experiment_tag
    )
    kick_count = _count_kicks_after_sent(
        session=session, experiment_tag=experiment_tag
    )

    return MetricCounters(
        sent=sent,
        suggested=suggested,
        skipped_total=skipped_total,
        failed=failed,
        private_conversion_count=private_conversion_count,
        kick_count=kick_count,
    )
