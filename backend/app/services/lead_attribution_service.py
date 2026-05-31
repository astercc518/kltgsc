"""
lead_attribution_service — Phase 11.

Surface the link between a CRM Lead and the group-AI PendingReply(s) that
caused it. The schema already carries PendingReply.lead_id (nullable FK to
lead.id), but Phase 4a–6 never populated it: lead_conversion_service only
counts conversions via an EXISTS subquery on (telegram_user_id, customer_id,
sent_at .. sent_at+window). Phase 11 actually writes the FK back so the CRM
can ask "which group reply produced this lead?".

Two entry points:

  link_pending_replies_for_lead(session, lead, window_hours=...)
    Best-effort write of PendingReply.lead_id = lead.id for every SENT
    PendingReply whose (source_user_id, customer_id) match this Lead and
    whose sent_at falls in [lead.created_at - window_hours, lead.created_at].
    Idempotent: only touches rows where lead_id IS NULL.

  backfill_unlinked_replies(session, *, since, window_hours=...)
    Sweep: every SENT PendingReply with sent_at >= since and lead_id IS NULL
    is checked against any same-tenant Lead inside the attribution window,
    and linked when one matches.

Tenant isolation: Lead.customer_id == PendingReply.customer_id is enforced
on every join, same constraint Phase 6 lead_conversion_service uses.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_
from sqlmodel import select

from app.models.lead import Lead
from app.models.pending_reply import PendingReply, PendingReplyStatus

logger = logging.getLogger(__name__)

# Default attribution window — same as lead_conversion_service. A Lead that
# materialises more than this many hours after the group reply is treated as
# unrelated (probably another channel converted them).
ATTRIBUTION_WINDOW_HOURS = 24

# Cap how many rows the backfill sweeps per tick so a single beat run can't
# stall on a huge historical backlog.
BACKFILL_BATCH_LIMIT = 500


def link_pending_replies_for_lead(
    session,
    lead: Lead,
    *,
    window_hours: int = ATTRIBUTION_WINDOW_HOURS,
) -> int:
    """
    Write PendingReply.lead_id = lead.id for every matching unlinked reply.

    Match: same (source_user_id, customer_id) AND sent_at in
    [lead.created_at - window_hours, lead.created_at]. Lead.customer_id must
    be set; otherwise we can't isolate tenant scope and bail out.

    Returns the number of PendingReply rows updated.
    """
    if lead.id is None or lead.customer_id is None or lead.created_at is None:
        return 0

    window_start = lead.created_at - timedelta(hours=window_hours)

    stmt = select(PendingReply).where(
        PendingReply.customer_id == lead.customer_id,
        PendingReply.source_user_id == lead.telegram_user_id,
        PendingReply.status == PendingReplyStatus.SENT.value,
        PendingReply.lead_id.is_(None),  # type: ignore[union-attr]
        PendingReply.sent_at.isnot(None),  # type: ignore[union-attr]
        PendingReply.sent_at >= window_start,
        PendingReply.sent_at <= lead.created_at,
    )

    updated = 0
    for row in session.exec(stmt).all():
        row.lead_id = lead.id
        session.add(row)
        updated += 1

    if updated:
        session.commit()
        logger.info(
            "lead_attribution: linked %d PendingReply rows to lead_id=%s "
            "(customer_id=%s, tg_user=%s)",
            updated, lead.id, lead.customer_id, lead.telegram_user_id,
        )
    return updated


def list_attribution_for_lead(
    session,
    *,
    lead_id: int,
    customer_id: int,
) -> List[PendingReply]:
    """
    Return all PendingReply rows already linked to the given lead, for the
    given tenant. Excludes nothing — both 'sent' and otherwise are returned
    if linked, because the link itself is the source-of-truth.
    """
    stmt = (
        select(PendingReply)
        .where(
            PendingReply.lead_id == lead_id,
            PendingReply.customer_id == customer_id,
        )
        .order_by(PendingReply.sent_at.desc())  # type: ignore[union-attr]
    )
    return list(session.exec(stmt).all())


def backfill_unlinked_replies(
    session,
    *,
    since: Optional[datetime] = None,
    window_hours: int = ATTRIBUTION_WINDOW_HOURS,
    limit: int = BACKFILL_BATCH_LIMIT,
) -> int:
    """
    Sweep unlinked SENT PendingReply rows and try to attach them to a Lead.

    `since` defaults to now - window_hours so we cover the natural attribution
    window plus a one-cycle cushion. Pass a larger window for a one-off
    historical backfill.

    Returns the total number of replies linked across all leads in this run.
    """
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours * 2)

    stmt = (
        select(PendingReply)
        .where(
            PendingReply.status == PendingReplyStatus.SENT.value,
            PendingReply.lead_id.is_(None),  # type: ignore[union-attr]
            PendingReply.sent_at.isnot(None),  # type: ignore[union-attr]
            PendingReply.sent_at >= since,
        )
        .order_by(PendingReply.sent_at.asc())  # type: ignore[union-attr]
        .limit(limit)
    )

    candidates = list(session.exec(stmt).all())
    if not candidates:
        return 0

    linked = 0
    for reply in candidates:
        window_end = reply.sent_at + timedelta(hours=window_hours)
        lead_stmt = (
            select(Lead)
            .where(
                Lead.customer_id == reply.customer_id,
                Lead.telegram_user_id == reply.source_user_id,
                Lead.created_at >= reply.sent_at,
                Lead.created_at <= window_end,
            )
            .order_by(Lead.created_at.asc())
            .limit(1)
        )
        lead = session.exec(lead_stmt).first()
        if lead is None or lead.id is None:
            continue
        reply.lead_id = lead.id
        session.add(reply)
        linked += 1

    if linked:
        session.commit()
        logger.info(
            "lead_attribution.backfill: linked %d/%d unlinked replies "
            "(since=%s window_hours=%d)",
            linked, len(candidates), since.isoformat(), window_hours,
        )
    return linked
