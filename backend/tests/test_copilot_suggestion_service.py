"""copilot_suggestion: compose 失败 → 写 suggested + WebSocket 推 Inbox"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.copilot_suggestion_service import save_suggested_reply


@pytest.mark.asyncio
async def test_saves_and_broadcasts():
    pr = MagicMock(
        id=42, customer_id=1, chat_id=-100, source_user_id=999,
        reply_text=None, responder_account_id=10,
    )
    suggested_text = "USDT 大额场外 T+0 私聊详谈"
    with patch(
        "app.services.copilot_suggestion_service._update_pending_reply_status",
    ) as upd_mock, patch(
        "app.services.copilot_suggestion_service._broadcast_ws", new=AsyncMock(),
    ) as ws_mock:
        await save_suggested_reply(
            pending_reply=pr, suggested_text=suggested_text,
        )
    upd_mock.assert_called_once()
    ws_mock.assert_awaited_once()
    payload = ws_mock.call_args.args[0]
    assert payload["type"] == "ai_suggestion_pending"
    assert payload["pending_reply_id"] == 42
    assert payload["customer_id"] == 1
    assert payload["suggested_text"] == suggested_text


@pytest.mark.asyncio
async def test_ws_failure_does_not_block_save():
    pr = MagicMock(
        id=42, customer_id=1, chat_id=-100, source_user_id=999,
        reply_text=None, responder_account_id=10,
    )
    with patch(
        "app.services.copilot_suggestion_service._update_pending_reply_status",
    ) as upd_mock, patch(
        "app.services.copilot_suggestion_service._broadcast_ws",
        new=AsyncMock(side_effect=Exception("ws gone")),
    ):
        # 不应 raise
        await save_suggested_reply(
            pending_reply=pr, suggested_text="x",
        )
    upd_mock.assert_called_once()
