"""human_reply_detector: 5min 内是否有真人/其他号针对性回应"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.human_reply_detector import has_human_or_other_account_replied


def test_returns_false_when_no_subsequent_messages():
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = []
    result = has_human_or_other_account_replied(
        session=fake_session, customer_id=1, chat_id=-100,
        source_message_id=42, source_user_id=999,
        solution_topic="USDT", since=datetime.now(timezone.utc),
        window_minutes=5,
    )
    assert result["detected"] is False
    assert result["reason"] is None


def test_returns_true_when_reply_chain_targets_source():
    """有 reply_to_msg_id == source_message_id 的后续消息 → 命中"""
    later = datetime.now(timezone.utc) + timedelta(minutes=1)
    fake_msg = MagicMock(
        sender_id=8888, reply_to_msg_id=42, content="对啊我有渠道",
        message_date=later,
    )
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [fake_msg]
    result = has_human_or_other_account_replied(
        session=fake_session, customer_id=1, chat_id=-100,
        source_message_id=42, source_user_id=999,
        solution_topic="USDT", since=datetime.now(timezone.utc),
        window_minutes=5,
    )
    assert result["detected"] is True
    assert result["reason"] == "reply_chain"


def test_returns_true_when_solution_topic_keyword_appears():
    """无 reply chain 但有人提到 solution_topic 关键词 → 弱命中"""
    later = datetime.now(timezone.utc) + timedelta(minutes=2)
    fake_msg = MagicMock(
        sender_id=7777, reply_to_msg_id=None,
        content="我也有 USDT 大额场外, 私聊", message_date=later,
    )
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [fake_msg]
    result = has_human_or_other_account_replied(
        session=fake_session, customer_id=1, chat_id=-100,
        source_message_id=42, source_user_id=999,
        solution_topic="USDT 大额场外", since=datetime.now(timezone.utc),
        window_minutes=5,
    )
    assert result["detected"] is True
    assert result["reason"] == "keyword_cooccur"


def test_ignores_source_user_self_replies():
    """source_user_id 自己后续的发言不算"""
    later = datetime.now(timezone.utc) + timedelta(minutes=1)
    fake_msg = MagicMock(
        sender_id=999, reply_to_msg_id=42, content="补充: 100k",
        message_date=later,
    )
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [fake_msg]
    result = has_human_or_other_account_replied(
        session=fake_session, customer_id=1, chat_id=-100,
        source_message_id=42, source_user_id=999,
        solution_topic="USDT", since=datetime.now(timezone.utc),
        window_minutes=5,
    )
    assert result["detected"] is False


def test_topic_must_split_into_real_tokens():
    """solution_topic 拆词, 短词 (< 2 字) 不算; 全停用词 → 不触发关键词共现"""
    later = datetime.now(timezone.utc) + timedelta(minutes=1)
    fake_msg = MagicMock(
        sender_id=7777, reply_to_msg_id=None,
        content="这个", message_date=later,  # 没命中任何 topic token
    )
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [fake_msg]
    result = has_human_or_other_account_replied(
        session=fake_session, customer_id=1, chat_id=-100,
        source_message_id=42, source_user_id=999,
        solution_topic="x",  # 单字符 topic, 拆词后无效
        since=datetime.now(timezone.utc),
        window_minutes=5,
    )
    assert result["detected"] is False
