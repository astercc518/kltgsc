"""RiskController Phase 1 单元测试 — 3 条规则"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.risk_controller import RiskDecision, decide_phase1
from app.models.pending_reply import PendingReplyStatus


def _pr(**overrides):
    base = dict(
        id=1, customer_id=1, monitor_id=1, chat_id=-100,
        source_user_id=9999, source_text="求 USDT",
        status=PendingReplyStatus.OBSERVING.value,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    base.update(overrides)
    return MagicMock(**base)


def _candidate_acc(id=10, customer_id=1):
    return MagicMock(id=id, customer_id=customer_id, role="worker", status="active")


def test_decide_skip_dup_within_48h():
    pr = _pr()
    sent_recently = [_pr(status=PendingReplyStatus.SENT.value, sent_at=datetime.now(timezone.utc) - timedelta(hours=20))]
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=sent_recently,
        account_daily_sent_count={10: 0},
        account_last_sent_in_chat={(10, -100): None},
        cooldown_minutes=120,
        daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_dup"


def test_decide_skip_throttled_when_no_candidate():
    pr = _pr()
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[],  # 无可用账号
        same_lead_sent_within_48h=[],
        account_daily_sent_count={},
        account_last_sent_in_chat={},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_no_account"


def test_decide_skip_throttled_all_over_quota():
    pr = _pr()
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 5},  # 已满
        account_last_sent_in_chat={(10, -100): None},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_throttled"


def test_decide_skip_cooldown():
    pr = _pr()
    last_sent = datetime.now(timezone.utc) - timedelta(minutes=30)  # 不足 cooldown
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 0},
        account_last_sent_in_chat={(10, -100): last_sent},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "skip"
    assert decision.skip_reason == "skipped_throttled"


def test_decide_compose_when_all_pass():
    pr = _pr()
    decision = decide_phase1(
        pending=pr,
        candidate_accounts=[_candidate_acc()],
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 0},
        account_last_sent_in_chat={(10, -100): None},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "compose"
    assert decision.responder_account_id == 10


def test_decide_compose_picks_first_eligible_when_multiple():
    """Phase 1: 候选多于 1 时, 取第一个 eligible (Phase 3 升级为加权随机)"""
    pr = _pr()
    accs = [_candidate_acc(id=10), _candidate_acc(id=11)]
    decision = decide_phase1(
        pending=pr, candidate_accounts=accs,
        same_lead_sent_within_48h=[],
        account_daily_sent_count={10: 0, 11: 0},
        account_last_sent_in_chat={(10, -100): None, (11, -100): None},
        cooldown_minutes=120, daily_quota=5,
    )
    assert decision.action == "compose"
    assert decision.responder_account_id == 10
