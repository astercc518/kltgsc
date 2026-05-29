"""group_reply_pipeline.entrypoint 早返路径 + 命中入库 (Phase 1 + Phase 2a)"""
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


# ---- Phase 1 Tests (early-return guards) ----

@pytest.mark.asyncio
async def test_entrypoint_skips_collector_role():
    """role=='collector' → 立即返回, 不写 DB"""
    msg = FakeMsg()
    acc = FakeAcc(role="collector")
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_observing") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "collector_role"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_no_customer():
    msg = FakeMsg()
    acc = FakeAcc(customer_id=None)
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline._insert_observing") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "no_customer"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_feature_off():
    msg = FakeMsg()
    acc = FakeAcc()
    monitor = FakeMonitor()
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", False), \
         patch("app.services.group_reply_pipeline._insert_observing") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "feature_off"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_skips_layer1_miss():
    """run_all_layers returns layer1_miss → no DB write"""
    msg = FakeMsg(text="今天天气真好")
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    fake_result = {
        "pass": False, "skip_reason": "layer1_miss",
        "layer1_matched": [], "layer2_similarity": None,
        "layer3": None, "borderline": False,
    }
    mock_customer = MagicMock(id=1)
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing") as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "layer1_miss"}
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_layer1_hit_inserts_pending_reply():
    """Layer 1 hit (via run_all_layers pass) → _insert_observing called with correct args"""
    msg = FakeMsg(text="求 USDT 100k", chat_id=-100, id=42, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})
    mock_pr = MagicMock(id=777)
    mock_customer = MagicMock(id=1)

    fake_result = {
        "pass": True,
        "layer1_matched": ["USDT"],
        "layer2_similarity": 0.65,
        "layer3": {
            "score": 80, "intent_type": "buy",
            "extracted_needs": ["100k USDT"],
            "suggested_solution_topic": "USDT 大额",
            "confidence": 0.88, "reason": "clear buy intent",
        },
        "borderline": False,
    }
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               return_value=mock_pr) as mocked:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"pending_reply_id": 777}
    assert mocked.call_count == 1
    kwargs = mocked.call_args.kwargs
    assert kwargs["chat_id"] == -100
    assert kwargs["message_id"] == 42
    assert kwargs["source_user_id"] == 999
    assert kwargs["source_text"] == "求 USDT 100k"
    assert kwargs["layer1_matched"] == ["USDT"]
    assert kwargs["layer2_similarity"] == 0.65
    assert kwargs["layer3"]["score"] == 80
    assert 60 <= kwargs["observation_window_seconds"] <= 900


# ---- Phase 2a Tests ----

@pytest.mark.asyncio
async def test_entrypoint_full_three_layers_passes_to_observing():
    """Layer 1+2+3 全 pass → 入 observing, layer3 字段已写入"""
    msg = FakeMsg(text="求 USDT 100k", chat_id=-100, id=42, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    mock_pr = MagicMock(id=777)
    mock_customer = MagicMock(id=1)
    fake_result = {
        "pass": True,
        "layer1_matched": ["USDT"],
        "layer2_similarity": 0.7,
        "layer3": {
            "score": 85, "intent_type": "buy",
            "extracted_needs": ["100k USDT"],
            "suggested_solution_topic": "USDT 大额", "confidence": 0.9, "reason": "x",
        },
        "borderline": False,
    }

    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               return_value=mock_pr):
        result = await entrypoint(msg, acc, monitor)
    assert result == {"pending_reply_id": 777}


@pytest.mark.asyncio
async def test_entrypoint_borderline_inserts_skipped_row():
    """layer3 borderline → 写一行 status=skipped_borderline, return skipped"""
    msg = FakeMsg(text="求 USDT 一般问", chat_id=-100, id=43, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    mock_pr = MagicMock(id=778)
    mock_customer = MagicMock(id=1)
    fake_result = {
        "pass": False, "skip_reason": "layer3_miss",
        "layer1_matched": ["USDT"], "layer2_similarity": 0.6,
        "layer3": {"score": 58, "intent_type": "ask", "extracted_needs": [],
                   "suggested_solution_topic": "x", "confidence": 0.8, "reason": "x"},
        "borderline": True,
    }
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_borderline",
               return_value=mock_pr):
        result = await entrypoint(msg, acc, monitor)
    assert result["skipped"] == "borderline"
    assert result["pending_reply_id"] == 778


@pytest.mark.asyncio
async def test_entrypoint_non_borderline_skip_no_db_write():
    """layer1_miss / 非 borderline 不写库"""
    msg = FakeMsg(text="天气好", chat_id=-100, id=44, sender_id=999)
    acc = FakeAcc()
    monitor = FakeMonitor(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"})

    fake_result = {
        "pass": False, "skip_reason": "layer1_miss",
        "layer1_matched": [], "layer2_similarity": None,
        "layer3": None, "borderline": False,
    }
    mock_customer = MagicMock(id=1)
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_borderline") as mocked_b, \
         patch("app.services.group_reply_pipeline._insert_observing") as mocked_o:
        result = await entrypoint(msg, acc, monitor)
    assert result == {"skipped": "layer1_miss"}
    mocked_b.assert_not_called()
    mocked_o.assert_not_called()
