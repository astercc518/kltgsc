"""Lead detector 三层串联 + 早返 + borderline 处理"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.lead_detector import run_all_layers


@pytest.mark.asyncio
async def test_run_all_pass():
    """三层都通过"""
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=[0.5]*768,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(
        keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"},
        keyword=None,
    )
    fake_llm_result = {
        "score": 80, "intent_type": "buy", "extracted_needs": ["100k"],
        "suggested_solution_topic": "USDT 大额", "confidence": 0.9, "reason": "x",
    }
    with patch(
        "app.services.lead_detector.layer2_icp_similarity",
        return_value={"pass": True, "similarity": 0.7, "degraded": False, "borderline": False},
    ), patch(
        "app.services.lead_detector._score_lead",
        new=AsyncMock(return_value=fake_llm_result),
    ), patch(
        "app.services.lead_detector._fetch_kb_top3",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.lead_detector._fetch_recent_context",
        new=AsyncMock(return_value=[]),
    ):
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="求 USDT 100k", chat_id=-100,
        )
    assert result["pass"] is True
    assert result["layer1_matched"] == ["USDT"]
    assert result["layer2_similarity"] == 0.7
    assert result["layer3"]["score"] == 80
    assert result.get("borderline") is False


@pytest.mark.asyncio
async def test_run_layer1_miss_short_circuits():
    fake_session = MagicMock()
    customer = MagicMock(icp_profile_embedding=None, lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7})
    monitor = MagicMock(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None)
    with patch(
        "app.services.lead_detector._score_lead", new=AsyncMock(),
    ) as mocked_score:
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="今天天气好", chat_id=-100,
        )
    assert result["pass"] is False
    assert result["skip_reason"] == "layer1_miss"
    mocked_score.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer2_miss():
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=[0.5]*768,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(
        keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None,
    )
    with patch(
        "app.services.lead_detector.layer2_icp_similarity",
        return_value={"pass": False, "similarity": 0.3, "degraded": False, "borderline": False},
    ), patch(
        "app.services.lead_detector._score_lead", new=AsyncMock(),
    ) as mocked_score:
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="求 USDT 但其实不相关", chat_id=-100,
        )
    assert result["pass"] is False
    assert result["skip_reason"] == "layer2_miss"
    mocked_score.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer3_borderline_reported():
    """Layer 3 score=58 落在 [55, 60) → pass=False + borderline=True"""
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=[0.5]*768,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None)
    with patch(
        "app.services.lead_detector.layer2_icp_similarity",
        return_value={"pass": True, "similarity": 0.7, "degraded": False, "borderline": False},
    ), patch(
        "app.services.lead_detector._score_lead",
        new=AsyncMock(return_value={
            "score": 58, "intent_type": "ask", "extracted_needs": [],
            "suggested_solution_topic": "x", "confidence": 0.8, "reason": "x",
        }),
    ), patch(
        "app.services.lead_detector._fetch_kb_top3", new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.lead_detector._fetch_recent_context", new=AsyncMock(return_value=[]),
    ):
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="USDT 一般问问", chat_id=-100,
        )
    assert result["pass"] is False
    assert result["skip_reason"] == "layer3_miss"
    assert result.get("borderline") is True


@pytest.mark.asyncio
async def test_run_layer2_degraded_skips_to_layer3():
    """customer.icp_embedding=None → Layer 2 降级 → 直接跑 Layer 3"""
    fake_session = MagicMock()
    customer = MagicMock(
        icp_profile_embedding=None,
        lead_detector_thresholds={"layer2_sim": 0.55, "layer3_score": 60, "layer3_confidence": 0.7},
    )
    monitor = MagicMock(keyword_filters={"include": ["USDT"], "exclude": [], "mode": "any"}, keyword=None)
    fake_llm = {
        "score": 85, "intent_type": "buy", "extracted_needs": ["x"],
        "suggested_solution_topic": "x", "confidence": 0.9, "reason": "x",
    }
    with patch(
        "app.services.lead_detector._score_lead", new=AsyncMock(return_value=fake_llm),
    ), patch(
        "app.services.lead_detector._fetch_kb_top3", new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.lead_detector._fetch_recent_context", new=AsyncMock(return_value=[]),
    ):
        result = await run_all_layers(
            session=fake_session, customer=customer, monitor=monitor,
            text="求 USDT", chat_id=-100,
        )
    assert result["pass"] is True
    assert result["layer2_similarity"] is None  # degraded
