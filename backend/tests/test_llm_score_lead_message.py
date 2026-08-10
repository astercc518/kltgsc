"""LLMService.score_lead_message — 结构化 JSON 输出"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.llm import LLMService


@pytest.mark.asyncio
async def test_score_lead_returns_full_schema():
    fake_json = {
        "score": 85,
        "intent_type": "buy",
        "extracted_needs": ["100k USDT 一次性买", "海外汇款"],
        "suggested_solution_topic": "USDT 大额场外结算",
        "confidence": 0.92,
        "reason": "明确询问 100k 量级 USDT 渠道",
    }
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(svc, "generate", new=AsyncMock(return_value=json.dumps(fake_json))):
        result = await svc.score_lead_message(
            text="想买 100k USDT 一次", icp_text="找 USDT 大额买家",
            kb_top3=[{"text": "USDT 场外结算"}], recent_context=[],
        )
    assert result["score"] == 85
    assert result["intent_type"] == "buy"
    assert "100k USDT" in result["extracted_needs"][0]
    assert result["suggested_solution_topic"] == "USDT 大额场外结算"
    assert result["confidence"] == 0.92


@pytest.mark.asyncio
async def test_score_lead_handles_llm_failure():
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(svc, "generate", new=AsyncMock(return_value=None)):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 0
    assert result["confidence"] == 0.0
    assert result["intent_type"] == "other"


@pytest.mark.asyncio
async def test_score_lead_handles_malformed_json():
    """LLM 输出不是合法 JSON → 兜底返回 score=0"""
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(
        svc, "generate", new=AsyncMock(return_value="not a json at all"),
    ):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 0


@pytest.mark.asyncio
async def test_score_lead_extracts_json_from_markdown_fence():
    """有时 LLM 会把 JSON 包在 ```json...``` 里, 应能 parse"""
    fake_json = {"score": 70, "intent_type": "ask", "extracted_needs": [],
                 "suggested_solution_topic": "x", "confidence": 0.8, "reason": "x"}
    wrapped = f"```json\n{json.dumps(fake_json)}\n```"
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(svc, "generate", new=AsyncMock(return_value=wrapped)):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 70


@pytest.mark.asyncio
async def test_score_lead_clamps_invalid_values():
    """LLM 返回 score=150 → clamp 到 100"""
    fake_json = {"score": 150, "intent_type": "buy", "extracted_needs": [],
                 "suggested_solution_topic": "x", "confidence": 1.5, "reason": "x"}
    fake_session = MagicMock()
    svc = LLMService(fake_session)
    with patch.object(
        svc, "generate", new=AsyncMock(return_value=json.dumps(fake_json)),
    ):
        result = await svc.score_lead_message(
            text="x", icp_text=None, kb_top3=[], recent_context=[],
        )
    assert result["score"] == 100
    assert result["confidence"] == 1.0
