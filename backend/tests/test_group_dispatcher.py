"""GroupDispatcher 单元测试 — typing 时延 + Telethon send + 扣费"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.group_dispatcher import dispatch_send


@pytest.mark.asyncio
async def test_dispatch_picks_delay_in_range():
    """时延在 (30, 120) 内"""
    pr = MagicMock(
        id=1, responder_account_id=10, chat_id=-100, reply_text="hi"
    )
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ) as sleep_mock:
        await dispatch_send(pr)
    delay_called = sleep_mock.call_args[0][0]
    assert 30 <= delay_called <= 120


@pytest.mark.asyncio
async def test_dispatch_calls_telethon_with_correct_args():
    pr = MagicMock(
        id=1, responder_account_id=10,
        chat_id=-100, reply_text="测试回复",
    )
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ) as send_mock, patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        await dispatch_send(pr)
    send_mock.assert_awaited_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["account_id"] == 10
    assert kwargs["chat_id"] == -100
    assert kwargs["text"] == "测试回复"


@pytest.mark.asyncio
async def test_dispatch_charges_after_send():
    pr = MagicMock(id=1, responder_account_id=10, chat_id=-100, reply_text="x")
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ) as charge, patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        await dispatch_send(pr)
    charge.assert_awaited_once_with(pending_reply=pr, amount_usd=0.50)


@pytest.mark.asyncio
async def test_dispatch_send_failure_skips_charge():
    pr = MagicMock(id=1, responder_account_id=10, chat_id=-100, reply_text="x")
    with patch(
        "app.services.group_dispatcher._telethon_send_to_group",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.services.group_dispatcher._charge_customer",
        new=AsyncMock(return_value=True),
    ) as charge, patch(
        "app.services.group_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        await dispatch_send(pr)
    charge.assert_not_called()
