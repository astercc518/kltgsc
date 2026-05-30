"""
Tests for app.services.account_lifecycle_tracker

Test 1 — record_event writes a row to the DB.
Test 2 — record_event is fail-soft: a broken session does not raise.
Test 3 — count_kicks_in_window counts correctly, respects window & event_type filter.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.account_lifecycle_tracker import record_event, count_kicks_in_window
from app.models.account_lifecycle_event import AccountLifecycleEvent
from app.models.account import Account


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account(session, phone="+10000000001") -> Account:
    acc = Account(phone_number=phone, session_string="", status="active")
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


# ---------------------------------------------------------------------------
# Test 1: record_event writes a row
# ---------------------------------------------------------------------------

def test_record_event_writes_row(session):
    """record_event should persist one AccountLifecycleEvent row."""
    acc = _make_account(session)

    record_event(
        session=session,
        account_id=acc.id,
        event_type="kicked_from_chat",
        chat_id=999,
        reason="kicked by admin",
        metadata={"group": "test_group"},
    )

    rows = session.exec(
        __import__("sqlmodel", fromlist=["select"]).select(AccountLifecycleEvent)
        .where(AccountLifecycleEvent.account_id == acc.id)
    ).all()

    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "kicked_from_chat"
    assert row.chat_id == 999
    assert row.reason == "kicked by admin"
    assert row.metadata_json == {"group": "test_group"}
    assert row.created_at is not None


# ---------------------------------------------------------------------------
# Test 2: record_event is fail-soft (no raise on DB error)
# ---------------------------------------------------------------------------

def test_record_event_fail_soft(session):
    """
    If the session raises on add/commit, record_event must NOT propagate the
    exception — it logs a warning and returns None.
    """
    broken_session = MagicMock()
    broken_session.add.side_effect = RuntimeError("DB gone")

    # Should not raise
    result = record_event(
        session=broken_session,
        account_id=99,
        event_type="session_invalid",
        reason="simulated failure",
    )
    assert result is None


# ---------------------------------------------------------------------------
# Test 3: count_kicks_in_window
# ---------------------------------------------------------------------------

def test_count_kicks_in_window(session):
    """
    count_kicks_in_window should:
    - count kicked_from_chat / session_invalid / banned events within the window
    - ignore events outside the window
    - ignore unrelated event_types (e.g. 'joined_chat')
    - return 0 for empty account_ids
    """
    acc = _make_account(session, phone="+10000000002")
    now = datetime.now(tz=timezone.utc)

    def _add(event_type, hours_ago):
        ev = AccountLifecycleEvent(
            account_id=acc.id,
            event_type=event_type,
            created_at=now - timedelta(hours=hours_ago),
        )
        session.add(ev)
    session.commit()

    # Within window, counted types
    _add("kicked_from_chat", 1)
    _add("session_invalid", 10)
    _add("banned", 24)
    # Within window, irrelevant type
    _add("joined_chat", 5)
    # Outside window (49 h ago, window=48)
    _add("kicked_from_chat", 49)
    session.commit()

    count = count_kicks_in_window(session=session, account_ids=[acc.id], window_hours=48)
    assert count == 3, f"Expected 3, got {count}"

    # Empty account_ids should return 0
    assert count_kicks_in_window(session=session, account_ids=[], window_hours=48) == 0
