"""
Phase 9 process_attempt real-flow tests with mocked pyrogram client.

Covers the state-machine paths that were placeholder in Phase 8:
  - successful join, no captcha → STATUS_JOINED + first_seen lifecycle event
  - join_chat raises UserAlreadyParticipant → STATUS_JOINED
  - join_chat raises generic error → STATUS_FAILED + kicked_from_chat
  - inline_button captcha success → STATUS_JOINED
  - inline_button captcha failure × 3 → STATUS_FAILED with captcha_attempts=3
  - inline_button captcha failure × 1 → STATUS_CAPTCHA (next-tick retry)
  - short_lived_client returns None → STATUS_FAILED with client_unavailable
"""
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from sqlmodel import SQLModel, Session, create_engine, select

from app.models.account_lifecycle_event import AccountLifecycleEvent  # noqa: F401
from app.models.captcha_event import CaptchaEvent
from app.models.join_attempt import (
    JoinAttempt,
    STATUS_CAPTCHA,
    STATUS_FAILED,
    STATUS_JOINED,
    STATUS_PENDING,
)


# ── shared engine + harness ──────────────────────────────────────────────────


def _make_engine():
    from app.models import customer  # noqa: F401
    from app.models import account  # noqa: F401
    from app.models import discovered_group  # noqa: F401
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


def _insert_attempt(eng, *, status=STATUS_PENDING, captcha_attempts=0,
                    customer_id=1, account_id=2,
                    chat_link="https://t.me/somegroup") -> int:
    now = datetime.now(timezone.utc)
    attempt = JoinAttempt(
        customer_id=customer_id, account_id=account_id,
        chat_link=chat_link, status=status,
        captcha_attempts=captcha_attempts, created_at=now, updated_at=now,
    )
    with Session(eng) as s:
        s.add(attempt); s.commit(); s.refresh(attempt)
    return attempt.id


@pytest.fixture(autouse=True)
def _patch_engine_and_sleep(monkeypatch):
    """
    Redirect all `engine` references used by join_orchestrator to a shared
    in-memory SQLite, and zero out the JOIN_OBSERVATION_SECONDS sleep so the
    suite stays fast.
    """
    eng = _make_engine()

    from app.services import join_orchestrator as orch

    monkeypatch.setattr(orch, "engine", eng)
    monkeypatch.setattr(orch, "JOIN_OBSERVATION_SECONDS", 0)

    # Skip the actual asyncio.sleep call (we still want the await to schedule).
    async def _instant_sleep(_seconds):
        return None
    monkeypatch.setattr(orch.asyncio, "sleep", _instant_sleep)

    # Provide a settled lifecycle session pointing at the same engine.
    import app.services.account_lifecycle_tracker as life
    yield eng


def _make_short_lived(client):
    """Returns an async context manager that yields `client`."""
    @asynccontextmanager
    async def _ctx(*, account_id):
        yield client
    return _ctx


def _patch_short_lived_client(monkeypatch, client):
    """Make process_attempt's short_lived_client yield this client."""
    import app.services.pyrogram_client_manager as pcm
    monkeypatch.setattr(pcm, "short_lived_client", _make_short_lived(client))
    from app.services import join_orchestrator as orch
    # process_attempt imports short_lived_client lazily; ensure the in-module
    # reference (if it was already imported) is also patched.
    if hasattr(orch, "short_lived_client"):
        monkeypatch.setattr(orch, "short_lived_client", _make_short_lived(client))


def _make_pyro_client(*, join_exception=None, history_messages=None,
                     dialogs=None):
    """Build a MagicMock pyrogram client with controllable behaviour."""
    client = MagicMock()
    if join_exception is None:
        client.join_chat = AsyncMock(return_value=None)
    else:
        client.join_chat = AsyncMock(side_effect=join_exception)

    async def _hist(chat_link, limit=5):
        for m in (history_messages or []):
            yield m
    client.get_chat_history = _hist

    async def _dialogs(limit=20):
        for d in (dialogs or []):
            yield d
    client.get_dialogs = _dialogs

    return client


def _msg(*, text="", buttons=None, has_photo=False, from_bot=False,
         from_user_id=None, chat_id=12345):
    """Build a pyrogram-shaped Message mock for get_chat_history."""
    m = MagicMock()
    m.text = text
    m.caption = ""
    m.photo = MagicMock() if has_photo else None

    chat = MagicMock()
    chat.id = chat_id
    m.chat = chat

    if from_user_id is not None or from_bot:
        u = MagicMock()
        u.id = from_user_id or 0
        u.is_bot = from_bot
        m.from_user = u
    else:
        m.from_user = None

    if buttons:
        rm = MagicMock()
        rm.inline_keyboard = [[
            type("Btn", (), {"text": b})() for b in buttons
        ]]
        m.reply_markup = rm
    else:
        m.reply_markup = None
    return m


# ── tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_join_no_captcha_marks_joined_and_records_first_seen(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng)

    # A single innocuous message: no buttons, no photo, no captcha indicators.
    benign = _msg(text="welcome everyone", from_bot=False, from_user_id=10)
    client = _make_pyro_client(history_messages=[benign], dialogs=[])
    _patch_short_lived_client(monkeypatch, client)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_JOINED
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
        events = s.exec(
            select(AccountLifecycleEvent).where(AccountLifecycleEvent.account_id == 2)
        ).all()
    assert row.status == STATUS_JOINED
    assert row.last_error is None
    assert any(e.event_type == "first_seen" for e in events)


@pytest.mark.asyncio
async def test_already_participant_treated_as_joined(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng)

    class UserAlreadyParticipantStub(Exception):
        pass

    client = _make_pyro_client(join_exception=UserAlreadyParticipantStub("dup"))
    _patch_short_lived_client(monkeypatch, client)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_JOINED
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
    assert row.status == STATUS_JOINED


@pytest.mark.asyncio
async def test_join_error_marks_failed_and_records_kicked(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng)

    client = _make_pyro_client(join_exception=RuntimeError("chat_invalid"))
    _patch_short_lived_client(monkeypatch, client)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_FAILED
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
        events = s.exec(
            select(AccountLifecycleEvent).where(AccountLifecycleEvent.account_id == 2)
        ).all()
    assert row.status == STATUS_FAILED
    assert row.last_error is not None
    assert "join_error" in row.last_error
    assert any(e.event_type == "kicked_from_chat" for e in events)


@pytest.mark.asyncio
async def test_client_unavailable_marks_failed(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng)

    _patch_short_lived_client(monkeypatch, None)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_FAILED
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
    assert row.status == STATUS_FAILED
    assert "client_unavailable" in (row.last_error or "")


@pytest.mark.asyncio
async def test_inline_button_captcha_success_marks_joined(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng)

    captcha_msg = _msg(
        text="please verify you are human",
        buttons=["I am human"],
        from_bot=True, from_user_id=999,
    )
    client = _make_pyro_client(history_messages=[captcha_msg])
    captcha_msg.click = AsyncMock(return_value=None)
    _patch_short_lived_client(monkeypatch, client)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_JOINED
    captcha_msg.click.assert_awaited_once()
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
        events = s.exec(select(CaptchaEvent).where(CaptchaEvent.join_attempt_id == attempt_id)).all()
    assert row.status == STATUS_JOINED
    assert row.captcha_type == "inline_button"
    assert row.captcha_attempts == 1
    assert any(e.handler == "inline_button" and e.succeeded for e in events)


@pytest.mark.asyncio
async def test_inline_button_captcha_first_failure_stays_in_captcha(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng)

    captcha_msg = _msg(
        text="verify human",
        buttons=["I am human"],
        from_bot=True, from_user_id=999,
    )
    captcha_msg.click = AsyncMock(side_effect=RuntimeError("button gone"))
    client = _make_pyro_client(history_messages=[captcha_msg])
    _patch_short_lived_client(monkeypatch, client)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_CAPTCHA
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
        events = s.exec(select(CaptchaEvent).where(CaptchaEvent.join_attempt_id == attempt_id)).all()
    assert row.status == STATUS_CAPTCHA
    assert row.captcha_attempts == 1
    assert any(e.handler == "inline_button" and not e.succeeded for e in events)


@pytest.mark.asyncio
async def test_inline_button_captcha_third_failure_marks_failed(monkeypatch, _patch_engine_and_sleep):
    eng = _patch_engine_and_sleep
    # Already failed twice, this is attempt #3.
    attempt_id = _insert_attempt(
        eng, status=STATUS_CAPTCHA, captcha_attempts=2,
    )

    captcha_msg = _msg(
        text="verify human",
        buttons=["I am human"],
        from_bot=True, from_user_id=999,
    )
    captcha_msg.click = AsyncMock(side_effect=RuntimeError("still broken"))
    client = _make_pyro_client(history_messages=[captcha_msg])
    _patch_short_lived_client(monkeypatch, client)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_FAILED
    with Session(eng) as s:
        row = s.get(JoinAttempt, attempt_id)
        events = s.exec(
            select(AccountLifecycleEvent).where(AccountLifecycleEvent.account_id == 2)
        ).all()
    assert row.status == STATUS_FAILED
    assert row.captcha_attempts == 3
    assert "captcha_failed" in (row.last_error or "")
    assert any(e.event_type == "kicked_from_chat" for e in events)


@pytest.mark.asyncio
async def test_settled_row_short_circuits(monkeypatch, _patch_engine_and_sleep):
    """An attempt already in STATUS_JOINED is returned as-is, no client work."""
    eng = _patch_engine_and_sleep
    attempt_id = _insert_attempt(eng, status=STATUS_JOINED)

    sentinel = MagicMock()
    sentinel.join_chat = AsyncMock(side_effect=AssertionError("should not run"))
    _patch_short_lived_client(monkeypatch, sentinel)

    from app.services.join_orchestrator import process_attempt
    result = await process_attempt(attempt_id=attempt_id)

    assert result == STATUS_JOINED
    sentinel.join_chat.assert_not_called()
