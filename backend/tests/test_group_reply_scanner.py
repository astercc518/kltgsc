"""Celery beat 扫描器: 拉到期 pending_replies + RiskController + ReplyComposer + Dispatch"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.workers.group_reply_scanner import scan_and_process_due_replies


@pytest.mark.asyncio
async def test_scanner_no_due_returns_zero():
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[]),
    ):
        processed = await scan_and_process_due_replies()
    assert processed == 0


@pytest.mark.asyncio
async def test_scanner_processes_one_compose_path():
    pr = MagicMock(
        id=1, customer_id=1, chat_id=-100, source_user_id=999,
        source_text="求 USDT", responder_account_id=None,
        layer3_solution_topic=None,
    )
    decision = MagicMock(action="compose", responder_account_id=10, skip_reason=None)

    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs_phase3",
        new=AsyncMock(return_value={
            "candidate_accounts": [],
            "personas_by_account": {10: {"style": "casual"}},
            "same_lead_sent_within_48h": [],
            "account_daily_sent_count": {},
            "account_last_sent_in_chat": {},
            "human_reply_signal": {"detected": False},
        }),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase3", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.Session",
        return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False)),
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase3",
        new=AsyncMock(return_value="测试回复"),
    ), patch(
        "app.workers.group_reply_scanner.dispatch_send", new=AsyncMock()
    ) as dispatch:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    dispatch.assert_awaited_once()
    assert pr.responder_account_id == 10
    assert pr.reply_text == "测试回复"


@pytest.mark.asyncio
async def test_scanner_skip_path_marks_status():
    pr = MagicMock(id=1, customer_id=1, chat_id=-100, source_user_id=999, source_text="x")
    decision = MagicMock(
        action="skip", skip_reason="skipped_dup", responder_account_id=None,
    )
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs_phase3",
        new=AsyncMock(return_value={
            "candidate_accounts": [],
            "personas_by_account": {},
            "same_lead_sent_within_48h": [],
            "account_daily_sent_count": {},
            "account_last_sent_in_chat": {},
            "human_reply_signal": {"detected": False},
        }),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase3", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner._mark_status", new=AsyncMock()
    ) as mark:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    mark.assert_awaited_once()
    assert mark.call_args.args[1] == "skipped_dup"


@pytest.mark.asyncio
async def test_scanner_compose_failure_routes_to_copilot():
    """compose 失败 → save_suggested_reply 被调"""
    pr = MagicMock(
        id=1, customer_id=1, chat_id=-100, source_user_id=999,
        source_text="x", message_id=42,
        layer3_solution_topic="USDT", created_at=datetime.now(timezone.utc),
    )
    decision = MagicMock(action="compose", responder_account_id=10, skip_reason=None, postpone_to=None)

    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs_phase3",
        new=AsyncMock(return_value={"candidate_accounts": [],
                                     "personas_by_account": {10: {"speaking_style": "casual"}},
                                     "same_lead_sent_within_48h": [],
                                     "account_daily_sent_count": {},
                                     "account_last_sent_in_chat": {},
                                     "human_reply_signal": {"detected": False}}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase3", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.Session",
        return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False)),
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase3",
        new=AsyncMock(return_value=None),  # 失败
    ), patch(
        "app.workers.group_reply_scanner.save_suggested_reply", new=AsyncMock(),
    ) as save_mock:
        n = await scan_and_process_due_replies()
    save_mock.assert_awaited_once()
    # 确认 suggested text 含原始消息
    call_kwargs = save_mock.call_args.kwargs
    assert "x" in call_kwargs["suggested_text"]
    assert "USDT" in call_kwargs["suggested_text"]


@pytest.mark.asyncio
async def test_scanner_postpone_path_updates_fire_at_keeps_observing():
    pr = MagicMock(
        id=1, customer_id=1, chat_id=-100, source_user_id=999, source_text="x",
        message_id=42, layer3_solution_topic="x", created_at=datetime.now(timezone.utc),
    )
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    decision = MagicMock(action="postpone", postpone_to=future, skip_reason=None, responder_account_id=None)

    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs_phase3",
        new=AsyncMock(return_value={
            "candidate_accounts": [],
            "personas_by_account": {},
            "same_lead_sent_within_48h": [],
            "account_daily_sent_count": {},
            "account_last_sent_in_chat": {},
            "human_reply_signal": {"detected": False},
        }),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase3", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner._postpone_pending_reply", new=AsyncMock(),
    ) as postpone_mock:
        n = await scan_and_process_due_replies()
    assert n == 1
    postpone_mock.assert_awaited_once()
