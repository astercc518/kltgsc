"""chitchat_dispatch: typing delay + Telethon 发 + chitchat_log"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.chitchat_dispatch import dispatch_chitchat


@pytest.mark.asyncio
async def test_dispatch_chitchat_happy_path():
    with patch(
        "app.services.chitchat_dispatch._telethon_send_chitchat",
        new=AsyncMock(return_value=True),
    ) as send_mock, patch(
        "app.services.chitchat_dispatch._insert_chitchat_log_row",
    ) as log_mock, patch(
        "app.services.chitchat_dispatch.asyncio.sleep", new=AsyncMock(),
    ):
        ok = await dispatch_chitchat(
            account_id=10, chat_id=-100, topic_id=5,
            text="今天天气不错", typing_delay=45,
        )
    assert ok is True
    send_mock.assert_awaited_once_with(account_id=10, chat_id=-100, text="今天天气不错")
    log_mock.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_chitchat_send_failure_skips_log():
    with patch(
        "app.services.chitchat_dispatch._telethon_send_chitchat",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.services.chitchat_dispatch._insert_chitchat_log_row",
    ) as log_mock, patch(
        "app.services.chitchat_dispatch.asyncio.sleep", new=AsyncMock(),
    ):
        ok = await dispatch_chitchat(
            account_id=10, chat_id=-100, topic_id=5,
            text="x", typing_delay=30,
        )
    assert ok is False
    log_mock.assert_not_called()
