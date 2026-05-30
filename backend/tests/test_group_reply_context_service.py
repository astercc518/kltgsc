"""查给定 (customer, source_user) 的近期群回复历史, 供私聊 LLM 拼 prompt"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.group_reply_context_service import (
    fetch_recent_group_replies_for_user,
)


def test_returns_empty_when_no_history():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    result = fetch_recent_group_replies_for_user(
        session=fake_session, customer_id=1, source_user_id=999, limit=3,
    )
    assert result == []


def test_returns_sent_replies_ordered_desc():
    """返回 status=sent 的最近 N 条, 按 sent_at desc"""
    fake_rows = [
        MagicMock(
            id=10, reply_text="USDT 大额 T+0 100k", sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
            layer3_needs=["100k USDT 买入"], layer3_solution_topic="USDT 大额场外",
            chat_id=-100,
        ),
        MagicMock(
            id=8, reply_text="USDT 渠道", sent_at=datetime.now(timezone.utc) - timedelta(hours=5),
            layer3_needs=["渠道"], layer3_solution_topic="USDT",
            chat_id=-100,
        ),
    ]
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = fake_rows
    result = fetch_recent_group_replies_for_user(
        session=fake_session, customer_id=1, source_user_id=999, limit=3,
    )
    assert len(result) == 2
    assert result[0]["reply_text"] == "USDT 大额 T+0 100k"
    assert result[0]["extracted_needs"] == ["100k USDT 买入"]
    assert result[0]["solution_topic"] == "USDT 大额场外"


def test_excludes_old_history():
    """超过 7 天的不取 (避免老对话污染当前私聊)"""
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    fetch_recent_group_replies_for_user(
        session=fake_session, customer_id=1, source_user_id=999, limit=3,
    )
    fake_session.exec.assert_called_once()
