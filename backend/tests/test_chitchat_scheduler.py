"""chitchat_scheduler: 每 5min tick, 按概率/配额/互斥发 chitchat"""
import pytest
import random
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.chitchat_scheduler import (
    chitchat_scheduler_tick, _decide_to_chitchat,
)


def test_decide_skips_when_quota_exhausted():
    persona = {"daily_chitchat_quota": 3}
    decision = _decide_to_chitchat(
        persona=persona, sent_today_count=3,
        hours_left_today=12, recent_business_reply=False,
        seed=0,
    )
    assert decision["fire"] is False
    assert decision["reason"] == "quota_exhausted"


def test_decide_skips_when_recent_business_reply():
    persona = {"daily_chitchat_quota": 7}
    decision = _decide_to_chitchat(
        persona=persona, sent_today_count=0,
        hours_left_today=12, recent_business_reply=True,
        seed=0,
    )
    assert decision["fire"] is False
    assert decision["reason"] == "business_reply_within_5min"


def test_decide_fires_with_probability():
    persona = {"daily_chitchat_quota": 7}
    fires = 0
    for s in range(100):
        d = _decide_to_chitchat(
            persona=persona, sent_today_count=0,
            hours_left_today=10, recent_business_reply=False,
            seed=s,
        )
        if d["fire"]:
            fires += 1
    # remaining=7, hours_left=10, prob ~= 7/10/12 ≈ 0.058 (每 5min, 12 次/h)
    # 100 次 seed 应该有部分命中
    assert fires > 0
    assert fires < 100  # 不是 100% 命中


@pytest.mark.asyncio
async def test_tick_skips_when_no_active_accounts():
    with patch(
        "app.workers.chitchat_scheduler._list_active_worker_accounts",
        return_value=[],
    ):
        processed = await chitchat_scheduler_tick()
    assert processed == 0


@pytest.mark.asyncio
async def test_tick_dispatches_chitchat_when_all_gates_pass():
    """All gates pass → dispatch_chitchat awaited (validates gather fix)"""
    fake_account = MagicMock(id=10, customer_id=1)
    fake_topic = MagicMock(id=5, prompt_template="今天天气不错")
    fake_persona = {
        "daily_chitchat_quota": 7,
        "active_hours": {"mon": [[0, 24]], "tue": [[0, 24]], "wed": [[0, 24]],
                         "thu": [[0, 24]], "fri": [[0, 24]], "sat": [[0, 24]], "sun": [[0, 24]]},
        "typing_delay_seconds_range": [30, 120],
        "speaking_style": "casual", "catchphrases": [],
    }
    with patch(
        "app.workers.chitchat_scheduler._list_active_worker_accounts",
        return_value=[fake_account],
    ), patch(
        "app.workers.chitchat_scheduler._list_joined_chats_for_account",
        return_value=[(-100, ["USDT"])],  # safe keyword — topic won't match
    ), patch(
        "app.workers.chitchat_scheduler.get_persona_for_account",
        return_value=fake_persona,
    ), patch(
        "app.workers.chitchat_scheduler._pick_random_chitchat_topic",
        return_value=fake_topic,
    ), patch(
        "app.workers.chitchat_scheduler._chitchat_log_count_today",
        return_value=0,
    ), patch(
        "app.workers.chitchat_scheduler._has_recent_business_reply",
        return_value=False,
    ), patch(
        "app.workers.chitchat_scheduler._decide_to_chitchat",
        return_value={"fire": True, "reason": None},
    ), patch(
        "app.workers.chitchat_scheduler._llm_render_chitchat",
        new=AsyncMock(return_value="今天天气不错出门带伞"),
    ), patch(
        "app.workers.chitchat_scheduler.dispatch_chitchat",
        new=AsyncMock(return_value=True),
    ) as dispatch_mock:
        n = await chitchat_scheduler_tick()
    assert n == 1
    dispatch_mock.assert_awaited_once()
    kwargs = dispatch_mock.call_args.kwargs
    assert kwargs["account_id"] == 10
    assert kwargs["chat_id"] == -100
    assert kwargs["topic_id"] == 5
    assert "天气不错" in kwargs["text"]


@pytest.mark.asyncio
async def test_tick_skips_topic_that_matches_monitor_keyword():
    """topic 命中本群 monitor.include 关键词 → 跳过 (避免触发自家 LeadDetector)"""
    fake_account = MagicMock(id=10, customer_id=1, joined_groups=[-100])
    fake_topic = MagicMock(id=5, prompt_template="USDT 大额场外结算")  # 命中
    fake_persona = {
        "daily_chitchat_quota": 7,
        "active_hours": {"mon": [[0, 24]], "tue": [[0, 24]], "wed": [[0, 24]],
                         "thu": [[0, 24]], "fri": [[0, 24]], "sat": [[0, 24]], "sun": [[0, 24]]},
        "typing_delay_seconds_range": [30, 120],
        "speaking_style": "casual", "catchphrases": [],
    }

    with patch(
        "app.workers.chitchat_scheduler._list_active_worker_accounts",
        return_value=[fake_account],
    ), patch(
        "app.workers.chitchat_scheduler._list_joined_chats_for_account",
        return_value=[(-100, ["USDT", "比特币"])],  # chat_id + monitor include keywords
    ), patch(
        "app.workers.chitchat_scheduler.get_persona_for_account",
        return_value=fake_persona,
    ), patch(
        "app.workers.chitchat_scheduler._pick_random_chitchat_topic",
        return_value=fake_topic,
    ), patch(
        "app.workers.chitchat_scheduler._chitchat_log_count_today",
        return_value=0,
    ), patch(
        "app.workers.chitchat_scheduler._has_recent_business_reply",
        return_value=False,
    ), patch(
        "app.workers.chitchat_scheduler._decide_to_chitchat",
        return_value={"fire": True, "reason": None},
    ), patch(
        "app.workers.chitchat_scheduler.dispatch_chitchat", new=AsyncMock(),
    ) as dispatch_mock:
        processed = await chitchat_scheduler_tick()
    # topic 含 "USDT" 命中 keyword → 不发
    dispatch_mock.assert_not_called()
    assert processed == 0
