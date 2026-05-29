"""group_reply_pipeline.entrypoint 早返路径 + 命中入库"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.group_reply_pipeline import entrypoint


class FakeMsg:
    def __init__(self, text="测试", chat_id=-100, id=1, sender_id=999):
        self.text = text
        self.chat_id = chat_id
        self.id = id
        self.sender_id = sender_id


class FakeAcc:
    def __init__(self, customer_id=1, role="worker"):
        self.id = 10
        self.customer_id = customer_id
        self.role = role


class FakeMonitor:
    def __init__(self, customer_id=1, keyword_filters=None, keyword=None):
        self.id = 5
        self.customer_id = customer_id
        self.keyword_filters = keyword_filters
        self.keyword = keyword


# ---- Tests ----

@pytest.mark.asyncio
async def test_entrypoint_skips_collector_role():
    """role=='collector' → 立即返回, 不写 DB"""
    msg = FakeMsg()
    acc = FakeAcc(role="collector")
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "collector_role"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_no_customer():
    msg = FakeMsg()
    acc = FakeAcc(customer_id=None)
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "no_customer"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_feature_off():
    msg = FakeMsg()
    acc = FakeAcc()
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", False), \
         patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "feature_off"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_layer1_miss():
    msg = FakeMsg(text="今天天气真好")
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_pending_reply") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "layer1_miss"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_layer1_hit_inserts_pending_reply():
    msg = FakeMsg(text="求 USDT 100k", chat_id=-100, id=42, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})
    mock_pr = MagicMock(id=777)
    # _insert_pending_reply is sync (repo uses sync SQLModel Session)
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_pending_reply",
               return_value=mock_pr) as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"pending_reply_id": 777}
    assert mocked.call_count == 1
    kwargs = mocked.call_args.kwargs
    assert kwargs["chat_id"] == -100
    assert kwargs["message_id"] == 42
    assert kwargs["source_user_id"] == 999
    assert kwargs["source_text"] == "求 USDT 100k"
    assert kwargs["layer1_matched"] == {"matched": ["USDT"]}
    assert 60 <= kwargs["observation_window_seconds"] <= 900
