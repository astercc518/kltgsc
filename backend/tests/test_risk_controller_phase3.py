"""RiskController.decide_phase3 — phase1 + active_hours + 真人接话 + 加权随机"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.risk_controller import RiskDecision, decide_phase3, ActiveHoursResult
from app.models.pending_reply import PendingReplyStatus


def _pr(**overrides):
    base = dict(
        id=1, customer_id=1, monitor_id=1, chat_id=-100,
        source_user_id=9999, source_text="求 USDT",
        message_id=42, layer3_solution_topic="USDT 大额场外",
        status=PendingReplyStatus.OBSERVING.value,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    base.update(overrides)
    return MagicMock(**base)


def _acc(id=10):
    return MagicMock(id=id, customer_id=1, role="worker", status="active")


def _persona(**overrides):
    base = {
        "display_name": "x", "speaking_style": "casual",
        "active_hours": {"mon": [[9, 18]], "tue": [[9, 18]], "wed": [[9, 18]],
                         "thu": [[9, 18]], "fri": [[9, 18]], "sat": [], "sun": []},
        "daily_reply_quota": 5, "per_chat_daily_quota": 2,
        "per_chat_cooldown_minutes": 120,
    }
    base.update(overrides)
    return base


def test_decide_postpones_when_outside_all_active_hours():
    """所有候选都不在活跃窗口 → action='postpone', fire_at 推到下一开窗"""
    pr = _pr()
    persona_off = _persona(active_hours={"mon": [], "tue": [], "wed": [],
                                          "thu": [], "fri": [], "sat": [], "sun": []})
    with patch(
        "app.services.risk_controller._is_within_active_hours",
        return_value=ActiveHoursResult(in_window=False, next_window_start=datetime.now(timezone.utc) + timedelta(hours=12)),
    ):
        decision = decide_phase3(
            pending=pr,
            candidate_accounts=[_acc()],
            personas_by_account={10: persona_off},
            same_lead_sent_within_48h=[],
            account_daily_sent_count={},
            account_last_sent_in_chat={},
            human_reply_signal={"detected": False, "reason": None},
        )
    assert decision.action == "postpone"
    assert decision.postpone_to is not None


def test_decide_skips_when_human_replied():
    pr = _pr()
    with patch(
        "app.services.risk_controller._is_within_active_hours",
        return_value=ActiveHoursResult(in_window=True, next_window_start=None),
    ):
        decision = decide_phase3(
            pending=pr,
            candidate_accounts=[_acc()],
            personas_by_account={10: _persona()},
            same_lead_sent_within_48h=[],
            account_daily_sent_count={},
            account_last_sent_in_chat={},
            human_reply_signal={"detected": True, "reason": "reply_chain"},
        )
    assert decision.action == "skip"
    assert decision.skip_reason == PendingReplyStatus.SKIPPED_HUMAN_REPLIED.value


def test_decide_falls_through_to_phase1_dedup():
    pr = _pr()
    sent_recent = [_pr(status=PendingReplyStatus.SENT.value)]
    with patch(
        "app.services.risk_controller._is_within_active_hours",
        return_value=ActiveHoursResult(in_window=True, next_window_start=None),
    ):
        decision = decide_phase3(
            pending=pr,
            candidate_accounts=[_acc()],
            personas_by_account={10: _persona()},
            same_lead_sent_within_48h=sent_recent,
            account_daily_sent_count={},
            account_last_sent_in_chat={},
            human_reply_signal={"detected": False, "reason": None},
        )
    assert decision.action == "skip"
    assert decision.skip_reason == PendingReplyStatus.SKIPPED_DUP.value


def test_decide_weighted_random_picks_one():
    """两个 eligible 候选, 加权随机选一个 (不保证具体, 但必须是 10 或 11)"""
    pr = _pr()
    accs = [_acc(10), _acc(11)]
    with patch(
        "app.services.risk_controller._is_within_active_hours",
        return_value=ActiveHoursResult(in_window=True, next_window_start=None),
    ):
        decision = decide_phase3(
            pending=pr,
            candidate_accounts=accs,
            personas_by_account={10: _persona(), 11: _persona()},
            same_lead_sent_within_48h=[],
            account_daily_sent_count={10: 0, 11: 0},
            account_last_sent_in_chat={(10, -100): None, (11, -100): None},
            human_reply_signal={"detected": False, "reason": None},
            seed=0,
        )
    assert decision.action == "compose"
    assert decision.responder_account_id in (10, 11)


def test_decide_weighted_higher_remaining_quota_more_likely():
    """剩余日额高的账号被选中概率高 (statistical, 取 100 次 seed)"""
    pr = _pr()
    accs = [_acc(10), _acc(11)]
    persona_low = _persona(daily_reply_quota=5)
    persona_high = _persona(daily_reply_quota=5)
    # 10 已发 4 (剩 1), 11 已发 0 (剩 5)
    with patch(
        "app.services.risk_controller._is_within_active_hours",
        return_value=ActiveHoursResult(in_window=True, next_window_start=None),
    ):
        wins = {10: 0, 11: 0}
        for seed in range(100):
            decision = decide_phase3(
                pending=pr,
                candidate_accounts=accs,
                personas_by_account={10: persona_low, 11: persona_high},
                same_lead_sent_within_48h=[],
                account_daily_sent_count={10: 4, 11: 0},
                account_last_sent_in_chat={(10, -100): None, (11, -100): None},
                human_reply_signal={"detected": False, "reason": None},
                seed=seed,
            )
            wins[decision.responder_account_id] += 1
    # 11 应该明显更频繁
    assert wins[11] > wins[10]


def test_decide_skip_no_candidate():
    pr = _pr()
    with patch(
        "app.services.risk_controller._is_within_active_hours",
        return_value=ActiveHoursResult(in_window=True, next_window_start=None),
    ):
        decision = decide_phase3(
            pending=pr,
            candidate_accounts=[],
            personas_by_account={},
            same_lead_sent_within_48h=[],
            account_daily_sent_count={},
            account_last_sent_in_chat={},
            human_reply_signal={"detected": False, "reason": None},
        )
    assert decision.action == "skip"
    assert decision.skip_reason == PendingReplyStatus.SKIPPED_NO_ACCOUNT.value
