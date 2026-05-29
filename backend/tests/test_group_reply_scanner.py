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
        "app.workers.group_reply_scanner._gather_risk_inputs",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase1", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.Session",
        return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False)),
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase2a",
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
        "app.workers.group_reply_scanner._gather_risk_inputs",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase1", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner._mark_status", new=AsyncMock()
    ) as mark:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    mark.assert_awaited_once()
    assert mark.call_args.args[1] == "skipped_dup"


@pytest.mark.asyncio
async def test_scanner_compose_failure_marks_failed():
    pr = MagicMock(id=1, customer_id=1, chat_id=-100, source_user_id=999, source_text="x",
                   layer3_solution_topic=None)
    decision = MagicMock(action="compose", responder_account_id=10, skip_reason=None)
    with patch(
        "app.workers.group_reply_scanner._fetch_due_pending_replies",
        new=AsyncMock(return_value=[pr]),
    ), patch(
        "app.workers.group_reply_scanner._gather_risk_inputs",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.workers.group_reply_scanner.decide_phase1", return_value=decision,
    ), patch(
        "app.workers.group_reply_scanner.Session",
        return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False)),
    ), patch(
        "app.workers.group_reply_scanner.compose_reply_phase2a",
        new=AsyncMock(return_value=None),  # 失败
    ), patch(
        "app.workers.group_reply_scanner._mark_status", new=AsyncMock()
    ) as mark:
        processed = await scan_and_process_due_replies()
    assert processed == 1
    # Phase 2a 失败 → status=failed
    assert mark.call_args.args[1] == "failed"
