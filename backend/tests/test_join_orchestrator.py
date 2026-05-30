"""
Tests for join_orchestrator Phase 8 Task 7.

Focus: state machine helpers + DB interaction.
Real Telethon integration is a placeholder; those tests live in staging.

test_queue_join_inserts_pending_row   — queue_join writes a pending row + returns id
test_insert_captcha_event_writes_audit — _insert_captcha_event persists audit record
test_update_attempt_mutates_fields     — _update_attempt changes status/last_error fields
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from sqlmodel import SQLModel, Session, create_engine, select

from app.models.join_attempt import JoinAttempt, STATUS_PENDING, STATUS_FAILED
from app.models.captcha_event import CaptchaEvent


# ── shared in-memory engine for tests ────────────────────────────────────────

def _make_engine():
    """Create a fresh in-memory SQLite engine with all required tables."""
    # We need to import all models that have foreign-key targets so SQLModel
    # creates them in the right order.
    from app.models import customer  # noqa: F401 — customer table
    from app.models import account   # noqa: F401 — account table
    from app.models import discovered_group  # noqa: F401 — discovered_group table
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


# ── helpers that accept an engine so we can inject the test engine ────────────

def _queue_join_with_engine(eng, *, customer_id, account_id, chat_link,
                              discovered_group_id=None):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    attempt = JoinAttempt(
        customer_id=customer_id, account_id=account_id,
        chat_link=chat_link, discovered_group_id=discovered_group_id,
        status=STATUS_PENDING, captcha_attempts=0,
        created_at=now, updated_at=now,
    )
    with Session(eng) as session:
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
    return attempt.id


def _insert_captcha_event_with_engine(
    eng, *, join_attempt_id, handler, succeeded,
    input_summary="", output_summary="", error_message=None,
):
    from datetime import datetime, timezone
    with Session(eng) as session:
        evt = CaptchaEvent(
            join_attempt_id=join_attempt_id, handler=handler,
            input_summary=input_summary, output_summary=output_summary,
            succeeded=succeeded, error_message=error_message,
            created_at=datetime.now(timezone.utc),
        )
        session.add(evt)
        session.commit()


def _update_attempt_with_engine(eng, *, attempt_id, **fields):
    from datetime import datetime, timezone
    with Session(eng) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        assert attempt is not None, f"attempt_id={attempt_id} not found"
        for k, v in fields.items():
            setattr(attempt, k, v)
        attempt.updated_at = datetime.now(timezone.utc)
        session.add(attempt)
        session.commit()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_queue_join_inserts_pending_row():
    """queue_join writes a STATUS_PENDING row and returns a valid int id."""
    eng = _make_engine()
    attempt_id = _queue_join_with_engine(
        eng,
        customer_id=1, account_id=2,
        chat_link="https://t.me/testgroup",
        discovered_group_id=None,
    )
    assert isinstance(attempt_id, int)
    assert attempt_id > 0

    with Session(eng) as session:
        row = session.get(JoinAttempt, attempt_id)
    assert row is not None
    assert row.status == STATUS_PENDING
    assert row.chat_link == "https://t.me/testgroup"
    assert row.customer_id == 1
    assert row.account_id == 2
    assert row.captcha_attempts == 0


def test_insert_captcha_event_writes_audit():
    """_insert_captcha_event persists a CaptchaEvent row with correct fields."""
    eng = _make_engine()
    # First insert a parent JoinAttempt
    attempt_id = _queue_join_with_engine(
        eng, customer_id=1, account_id=2,
        chat_link="https://t.me/somegroup",
    )

    _insert_captcha_event_with_engine(
        eng,
        join_attempt_id=attempt_id,
        handler="inline_button",
        succeeded=True,
        input_summary="Click I am human",
        output_summary="Clicked button",
        error_message=None,
    )

    with Session(eng) as session:
        events = session.exec(
            select(CaptchaEvent).where(CaptchaEvent.join_attempt_id == attempt_id)
        ).all()

    assert len(events) == 1
    evt = events[0]
    assert evt.handler == "inline_button"
    assert evt.succeeded is True
    assert evt.input_summary == "Click I am human"
    assert evt.output_summary == "Clicked button"
    assert evt.error_message is None


def test_update_attempt_mutates_fields():
    """_update_attempt changes status and last_error fields."""
    eng = _make_engine()
    attempt_id = _queue_join_with_engine(
        eng, customer_id=1, account_id=2,
        chat_link="https://t.me/another",
    )

    # Initial state
    with Session(eng) as session:
        before = session.get(JoinAttempt, attempt_id)
    assert before.status == STATUS_PENDING
    assert before.last_error is None

    # Mutate
    _update_attempt_with_engine(
        eng, attempt_id=attempt_id,
        status=STATUS_FAILED, last_error="network_timeout",
    )

    with Session(eng) as session:
        after = session.get(JoinAttempt, attempt_id)
    assert after.status == STATUS_FAILED
    assert after.last_error == "network_timeout"
