"""
Tests for app.services.safe_send_dispatcher — SafeSendConfig & SafeSendDispatcher.

Uses the in-memory SQLite session from conftest fixtures.
"""
from datetime import datetime, timedelta, date

import pytest

from app.services.safe_send_dispatcher import SafeSendConfig, SafeSendDispatcher
from app.models.account import Account
from app.models.account_stats import AccountSendStats


# ---------------------------------------------------------------------------
# SafeSendConfig
# ---------------------------------------------------------------------------

class TestSafeSendConfig:

    def test_defaults(self):
        cfg = SafeSendConfig()
        assert cfg.max_daily_sends_new == 15
        assert cfg.max_daily_sends_normal == 30
        assert cfg.max_daily_sends_trusted == 50
        assert cfg.min_delay_seconds == 60
        assert cfg.max_delay_seconds == 180
        assert cfg.sends_before_rest == 5

    def test_custom_values(self):
        cfg = SafeSendConfig(
            max_daily_sends_new=10,
            max_daily_sends_normal=25,
            max_daily_sends_trusted=40,
            min_delay_seconds=30,
            max_delay_seconds=90,
        )
        assert cfg.max_daily_sends_new == 10
        assert cfg.max_daily_sends_normal == 25
        assert cfg.max_daily_sends_trusted == 40
        assert cfg.min_delay_seconds == 30
        assert cfg.max_delay_seconds == 90

    def test_load_from_db_uses_defaults_when_empty(self, session):
        """When there are no SystemConfig rows, defaults should apply."""
        cfg = SafeSendConfig.load_from_db(session)
        assert cfg.max_daily_sends_new == 15
        assert cfg.max_daily_sends_normal == 30

    def test_load_from_db_overrides_from_rows(self, session):
        """Insert SystemConfig rows and verify they override defaults."""
        from app.models.system_config import SystemConfig

        session.add(SystemConfig(key="safe_send_max_daily_sends_new", value="20"))
        session.add(SystemConfig(key="safe_send_min_delay_seconds", value="45"))
        session.commit()

        cfg = SafeSendConfig.load_from_db(session)
        assert cfg.max_daily_sends_new == 20
        assert cfg.min_delay_seconds == 45
        # Untouched fields keep defaults
        assert cfg.max_daily_sends_normal == 30


# ---------------------------------------------------------------------------
# Daily limit calculation
# ---------------------------------------------------------------------------

class TestGetAccountDailyLimit:

    def test_new_account_limit(self, session, new_account):
        dispatcher = SafeSendDispatcher(session)
        limit = dispatcher.get_account_daily_limit(new_account)
        assert limit == 15  # max_daily_sends_new

    def test_normal_account_limit(self, session, sample_account):
        """sample_account is 15 days old => normal tier."""
        dispatcher = SafeSendDispatcher(session)
        limit = dispatcher.get_account_daily_limit(sample_account)
        assert limit == 30  # max_daily_sends_normal

    def test_trusted_account_limit(self, session, trusted_account):
        dispatcher = SafeSendDispatcher(session)
        limit = dispatcher.get_account_daily_limit(trusted_account)
        assert limit == 50  # max_daily_sends_trusted

    def test_account_without_created_at(self, session):
        """If created_at is None, should return the normal tier limit."""
        account = Account(
            phone_number="+9999999999",
            session_string="",
            status="active",
        )
        session.add(account)
        session.commit()
        # Manually set to None after commit to bypass default_factory
        account.created_at = None

        dispatcher = SafeSendDispatcher(session)
        limit = dispatcher.get_account_daily_limit(account)
        assert limit == 30  # max_daily_sends_normal


# ---------------------------------------------------------------------------
# Send delay
# ---------------------------------------------------------------------------

class TestGetSendDelay:

    def test_delay_within_range(self, session):
        cfg = SafeSendConfig(min_delay_seconds=60, max_delay_seconds=180)
        dispatcher = SafeSendDispatcher(session, config=cfg)
        for _ in range(50):
            delay = dispatcher.get_send_delay()
            assert 60 <= delay <= 180


# ---------------------------------------------------------------------------
# Rest logic
# ---------------------------------------------------------------------------

class TestShouldRest:

    def test_no_rest_needed(self, session):
        dispatcher = SafeSendDispatcher(session)
        stats = AccountSendStats(
            account_id=1,
            stat_date=date.today(),
            consecutive_sends=3,
        )
        needs_rest, duration = dispatcher.should_rest(stats)
        assert needs_rest is False
        assert duration == 0

    def test_rest_needed_after_threshold(self, session):
        cfg = SafeSendConfig(sends_before_rest=5, rest_duration_min=300, rest_duration_max=900)
        dispatcher = SafeSendDispatcher(session, config=cfg)
        stats = AccountSendStats(
            account_id=1,
            stat_date=date.today(),
            consecutive_sends=5,
        )
        needs_rest, duration = dispatcher.should_rest(stats)
        assert needs_rest is True
        assert 300 <= duration <= 900


# ---------------------------------------------------------------------------
# Send plan generation
# ---------------------------------------------------------------------------

class TestCreateSendPlan:

    def test_plan_with_sufficient_capacity(self, session, sample_account):
        dispatcher = SafeSendDispatcher(session)
        plan = dispatcher.create_send_plan(
            account_ids=[sample_account.id],
            target_user_ids=list(range(10)),  # 10 targets
        )
        assert plan["total_targets"] == 10
        assert plan["can_complete_today"] is True
        assert plan["batches_needed"] == 1
        assert plan["sends_today"] == 10

    def test_plan_with_insufficient_capacity(self, session, new_account):
        """A new account can send 15/day.  Give it 50 targets."""
        dispatcher = SafeSendDispatcher(session)
        plan = dispatcher.create_send_plan(
            account_ids=[new_account.id],
            target_user_ids=list(range(50)),
        )
        assert plan["total_targets"] == 50
        assert plan["can_complete_today"] is False
        assert plan["batches_needed"] > 1
        assert plan["sends_remaining"] > 0

    def test_plan_estimated_hours_positive(self, session, sample_account):
        dispatcher = SafeSendDispatcher(session)
        plan = dispatcher.create_send_plan(
            account_ids=[sample_account.id],
            target_user_ids=list(range(20)),
        )
        assert plan["estimated_hours_today"] > 0

    def test_plan_no_accounts(self, session):
        """With no account IDs, capacity is zero."""
        dispatcher = SafeSendDispatcher(session)
        plan = dispatcher.create_send_plan(
            account_ids=[],
            target_user_ids=list(range(10)),
        )
        assert plan["total_capacity_today"] == 0
        assert plan["can_complete_today"] is False


# ---------------------------------------------------------------------------
# get_or_create_stats
# ---------------------------------------------------------------------------

class TestGetOrCreateStats:

    def test_creates_new_stats(self, session, sample_account):
        dispatcher = SafeSendDispatcher(session)
        today = date.today()
        stats = dispatcher.get_or_create_stats(sample_account.id, today)
        assert stats.account_id == sample_account.id
        assert stats.stat_date == today
        assert stats.send_count == 0

    def test_returns_existing_stats(self, session, sample_account):
        dispatcher = SafeSendDispatcher(session)
        today = date.today()
        s1 = dispatcher.get_or_create_stats(sample_account.id, today)
        s1.send_count = 7
        session.add(s1)
        session.commit()

        s2 = dispatcher.get_or_create_stats(sample_account.id, today)
        assert s2.id == s1.id
        assert s2.send_count == 7
