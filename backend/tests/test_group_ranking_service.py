"""Group ranking service unit tests."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.group_ranking_service import compute_score, is_chat_already_monitored


def test_score_zero_for_empty_input():
    score = compute_score(
        members_count=None, daily_messages=None, category=None,
        customer_icp_keywords=[], is_already_monitored=False,
    )
    assert score == 0.0


def test_score_high_for_active_matched_group():
    score = compute_score(
        members_count=50000, daily_messages=500,
        category="Cryptocurrency OTC",
        customer_icp_keywords=["OTC", "USDT", "Cryptocurrency"],
        is_already_monitored=False,
        discovered_at=datetime.now(timezone.utc),
    )
    assert score > 60


def test_score_penalty_when_already_monitored():
    base = compute_score(
        members_count=10000, daily_messages=200, category="Crypto",
        customer_icp_keywords=["Crypto"], is_already_monitored=False,
    )
    penalized = compute_score(
        members_count=10000, daily_messages=200, category="Crypto",
        customer_icp_keywords=["Crypto"], is_already_monitored=True,
    )
    assert penalized < base
    assert base - penalized == 30.0


def test_is_already_monitored_finds_username():
    fake_session = MagicMock()
    fake_monitor = MagicMock(target_groups="@usdt_otc,@other_group")
    fake_session.exec.return_value.all.return_value = [fake_monitor]
    assert is_chat_already_monitored(
        session=fake_session, customer_id=1,
        chat_username="usdt_otc", chat_id=None,
    ) is True


def test_is_already_monitored_returns_false_when_not_found():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    assert is_chat_already_monitored(
        session=fake_session, customer_id=1,
        chat_username="new_group", chat_id=None,
    ) is False
