"""ReplyComposer Phase 1 — KB-only 三段式生成"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.reply_composer import compose_reply_phase1


@pytest.mark.asyncio
async def test_compose_returns_str_within_length():
    fake_kb_hits = [
        {"text": "USDT 大额场外结算通常 T+0 到账", "score": 0.9},
        {"text": "汇率优于交易所现价 0.3%", "score": 0.85},
    ]
    fake_llm_output = "USDT 大额 T+0 直接到账, 汇率优交易所 0.3%. 私聊我"
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=fake_kb_hits),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value=fake_llm_output),
    ):
        result = await compose_reply_phase1(
            customer_id=1,
            source_text="想买 100k USDT",
            solution_topic="USDT 大额场外",
        )
    assert isinstance(result, str)
    assert 5 <= len(result) <= 80
    assert "USDT" in result


@pytest.mark.asyncio
async def test_compose_anti_hallucination_filters_exposure():
    fake_kb_hits = [{"text": "USDT 渠道", "score": 0.9}]
    # LLM 不慎吐 "+V"  → filter 应去掉
    fake_llm_output = "USDT 直供, 我有真实案例, 加我 +V 详谈"
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=fake_kb_hits),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value=fake_llm_output),
    ):
        result = await compose_reply_phase1(
            customer_id=1, source_text="USDT", solution_topic="USDT",
        )
    assert "+V" not in result
    assert "加我" not in result or "加我 +V" not in result


@pytest.mark.asyncio
async def test_compose_retries_then_returns_suggested_on_persistent_fail():
    """LLM 一直吐暴露词 → 2 次失败后返回 None (Phase 4 接管转 suggested)"""
    fake_kb_hits = [{"text": "USDT", "score": 0.9}]
    bad_output = "作为 AI 助手, 我是大模型"
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=fake_kb_hits),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value=bad_output),
    ):
        result = await compose_reply_phase1(
            customer_id=1, source_text="x", solution_topic="x",
        )
    # Phase 1: 失败返回 None, 上层置 status=failed (Phase 4 改成 suggested)
    assert result is None


@pytest.mark.asyncio
async def test_compose_empty_kb_still_attempts():
    """KB 无召回也尝试生成 (Phase 1 容错; Phase 2 会用 case_studies 兜底)"""
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="一句话方案 一句话效果 私聊我"),
    ):
        result = await compose_reply_phase1(
            customer_id=1, source_text="x", solution_topic="x",
        )
    assert result is not None
