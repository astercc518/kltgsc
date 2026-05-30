"""
lead_conversion_service — 查 source_user 在 sent 后 N 小时内私聊转化

After F1+F2 refactor: the service issues a SINGLE session.exec() call that
returns a scalar count (not a list of sent rows).  Mocks are updated to
match this single-query interface.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.lead_conversion_service import (
    count_private_conversions_for_experiment,
)


def _make_session(count_value: int) -> MagicMock:
    """Return a fake session whose exec().first() yields count_value."""
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = count_value
    return fake_session


def test_returns_zero_when_no_conversions():
    """DB returns 0 → function returns 0."""
    cnt = count_private_conversions_for_experiment(
        session=_make_session(0), experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 0


def test_returns_one_conversion():
    """DB returns 1 → function returns 1."""
    cnt = count_private_conversions_for_experiment(
        session=_make_session(1), experiment_tag="exp:v1", window_hours=24,
    )
    assert cnt == 1


def test_returns_two_conversions():
    """DB returns 2 → function returns 2 (distinct sent rows)."""
    cnt = count_private_conversions_for_experiment(
        session=_make_session(2), experiment_tag="exp:v2", window_hours=24,
    )
    assert cnt == 2


def test_returns_partial_count():
    """DB returns arbitrary int (e.g. 5) → function passes it through."""
    cnt = count_private_conversions_for_experiment(
        session=_make_session(5), experiment_tag="exp:v3", window_hours=48,
    )
    assert cnt == 5


def test_handles_none_from_first():
    """session.exec().first() returns None (empty result) → function returns 0."""
    fake_session = MagicMock()
    fake_session.exec.return_value.first.return_value = None
    cnt = count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v4", window_hours=24,
    )
    assert cnt == 0


def test_single_exec_call():
    """Verify that only ONE exec() is issued — no N+1 queries."""
    fake_session = _make_session(3)
    count_private_conversions_for_experiment(
        session=fake_session, experiment_tag="exp:v5", window_hours=24,
    )
    assert fake_session.exec.call_count == 1
