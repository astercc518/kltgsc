"""
Phase 11 lead_attribution_service tests.

Verify the link + backfill helpers do exactly what their docstrings claim:
- write PendingReply.lead_id only on matching SENT rows inside the window
- never overwrite a lead_id that was already set
- enforce same-tenant isolation
- backfill picks up historical rows but is bounded by `since` + `limit`
"""
import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlmodel import Session, SQLModel, create_engine

from app.models.lead import Lead
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.services.lead_attribution_service import (
    backfill_unlinked_replies,
    link_pending_replies_for_lead,
    list_attribution_for_lead,
)


def _make_engine():
    # Pull in all FK targets so SQLModel.metadata.create_all works.
    from app.models import account, customer, keyword_monitor  # noqa: F401
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _insert_lead(session, *, customer_id, telegram_user_id, created_at=None):
    lead = Lead(
        account_id=1,
        customer_id=customer_id,
        telegram_user_id=telegram_user_id,
        username=f"user{telegram_user_id}",
        status="new",
        created_at=created_at or _now(),
    )
    session.add(lead); session.commit(); session.refresh(lead)
    return lead


_reply_id_seq = [1000]


def _next_reply_id() -> int:
    _reply_id_seq[0] += 1
    return _reply_id_seq[0]


def _insert_reply(
    session, *, customer_id, source_user_id, sent_at,
    status=PendingReplyStatus.SENT.value, lead_id=None,
    monitor_id=1, chat_id=-100_111_222,
):
    """SQLite's BigInteger PK doesn't auto-increment; assign explicit ids."""
    now = _now()
    reply = PendingReply(
        id=_next_reply_id(),
        customer_id=customer_id,
        monitor_id=monitor_id,
        chat_id=chat_id,
        message_id=42,
        source_user_id=source_user_id,
        source_text="hi I need OTC",
        reply_text="reach out via DM",
        status=status,
        created_at=now,
        sent_at=sent_at,
        lead_id=lead_id,
    )
    session.add(reply); session.commit(); session.refresh(reply)
    return reply


def test_link_matches_pending_reply_within_window():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        reply = _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=2),
        )

        linked = link_pending_replies_for_lead(s, lead)
        assert linked == 1

        s.refresh(reply)
        assert reply.lead_id == lead.id


def test_link_skips_outside_window():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        # Reply sent 48h before Lead — outside default 24h window
        reply = _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=48),
        )

        linked = link_pending_replies_for_lead(s, lead)
        assert linked == 0

        s.refresh(reply)
        assert reply.lead_id is None


def test_link_enforces_tenant_isolation():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        # Same user, different customer — must NOT link
        reply = _insert_reply(
            s, customer_id=2, source_user_id=999,
            sent_at=now - timedelta(hours=2),
        )

        linked = link_pending_replies_for_lead(s, lead)
        assert linked == 0

        s.refresh(reply)
        assert reply.lead_id is None


def test_link_idempotent_does_not_overwrite():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        # Pre-existing link to a different lead must be preserved
        reply = _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=2),
            lead_id=12345,
        )

        linked = link_pending_replies_for_lead(s, lead)
        assert linked == 0

        s.refresh(reply)
        assert reply.lead_id == 12345


def test_link_skips_non_sent_status():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        # composing status -- not eligible
        reply = _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=2),
            status=PendingReplyStatus.COMPOSING.value,
        )

        linked = link_pending_replies_for_lead(s, lead)
        assert linked == 0

        s.refresh(reply)
        assert reply.lead_id is None


def test_list_attribution_returns_linked_replies_only():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=1),
        )
        _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=2),
        )
        # an unrelated unlinked reply
        unlinked = _insert_reply(
            s, customer_id=1, source_user_id=888,
            sent_at=now - timedelta(hours=1),
        )

        link_pending_replies_for_lead(s, lead)
        rows = list_attribution_for_lead(
            s, lead_id=lead.id, customer_id=1,
        )
        assert len(rows) == 2
        assert all(r.lead_id == lead.id for r in rows)
        assert unlinked.id not in {r.id for r in rows}


def test_backfill_links_matching_unlinked_replies():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        lead = _insert_lead(
            s, customer_id=1, telegram_user_id=999, created_at=now,
        )
        reply = _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=1),
        )

        # No prior call; backfill should pick it up
        linked = backfill_unlinked_replies(s)
        assert linked == 1

        s.refresh(reply)
        assert reply.lead_id == lead.id


def test_backfill_since_window_bounds_scan():
    eng = _make_engine()
    with Session(eng) as s:
        now = _now()
        # Lead at now
        _insert_lead(s, customer_id=1, telegram_user_id=999, created_at=now)
        # Reply > since cutoff (will NOT be touched)
        ancient = _insert_reply(
            s, customer_id=1, source_user_id=999,
            sent_at=now - timedelta(hours=72),
        )

        linked = backfill_unlinked_replies(
            s, since=now - timedelta(hours=24),
        )
        assert linked == 0

        s.refresh(ancient)
        assert ancient.lead_id is None
