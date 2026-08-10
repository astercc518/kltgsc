"""pipeline 写 experiment_tag 字段当有 applicable experiment"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.group_reply_pipeline import entrypoint


class FakeMsg:
    text = "求 USDT"; chat_id = -100; id = 42; sender_id = 999


class FakeAcc:
    id = 10; customer_id = 1; role = "worker"


class FakeMonitor:
    id = 5; customer_id = 1
    keyword_filters = {"include": ["USDT"], "exclude": [], "mode": "any"}
    keyword = None


@pytest.mark.asyncio
async def test_entrypoint_writes_experiment_tag_when_experiment_exists():
    mock_pr = MagicMock(id=777)
    mock_customer = MagicMock(id=1, lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7})

    fake_experiment = MagicMock(id=1, variants=[
        {"tag": "v1", "weight": 0.5, "params": {"layer3_score": 60}},
        {"tag": "v2", "weight": 0.5, "params": {"layer3_score": 70}},
    ])
    fake_experiment.name = "exp_layer3_score"

    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer

    fake_result = {
        "pass": True, "layer1_matched": ["USDT"], "layer2_similarity": 0.7,
        "layer3": {"score": 80, "intent_type": "buy", "extracted_needs": [],
                   "suggested_solution_topic": "x", "confidence": 0.9, "reason": "x"},
        "borderline": False,
    }

    captured = {}
    def fake_insert_observing(**kw):
        captured.update(kw)
        return mock_pr

    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.find_applicable_experiments",
               return_value=[fake_experiment]), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               side_effect=fake_insert_observing):
        result = await entrypoint(FakeMsg(), FakeAcc(), FakeMonitor())
    assert result == {"pending_reply_id": 777}
    assert captured.get("experiment_tag") in ("exp_layer3_score:v1", "exp_layer3_score:v2")


@pytest.mark.asyncio
async def test_entrypoint_no_experiment_tag_when_no_experiments():
    mock_pr = MagicMock(id=778)
    mock_customer = MagicMock(id=1, lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7})
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    fake_session.get.return_value = mock_customer
    fake_result = {
        "pass": True, "layer1_matched": ["USDT"], "layer2_similarity": 0.7,
        "layer3": {"score": 80, "intent_type": "buy", "extracted_needs": [],
                   "suggested_solution_topic": "x", "confidence": 0.9, "reason": "x"},
        "borderline": False,
    }
    captured = {}
    def fake_insert(**kw):
        captured.update(kw); return mock_pr
    with patch("app.services.group_reply_pipeline.GROUP_AI_REPLY_ENABLED", True), \
         patch("app.services.group_reply_pipeline.Session", return_value=fake_session), \
         patch("app.services.group_reply_pipeline.find_applicable_experiments",
               return_value=[]), \
         patch("app.services.group_reply_pipeline.run_all_layers",
               new=AsyncMock(return_value=fake_result)), \
         patch("app.services.group_reply_pipeline._insert_observing",
               side_effect=fake_insert):
        result = await entrypoint(FakeMsg(), FakeAcc(), FakeMonitor())
    assert result == {"pending_reply_id": 778}
    assert captured.get("experiment_tag") is None
