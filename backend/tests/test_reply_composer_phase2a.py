"""ReplyComposer Phase 2a: 接入 case_studies + 数字一致性反幻觉"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.reply_composer import (
    compose_reply_phase2a, _extract_numbers, _numeric_consistency_ok,
)


def test_extract_numbers_simple():
    assert _extract_numbers("100k USDT") == {"100k"}
    assert _extract_numbers("3 天到账, 30 万美金") == {"3", "30", "30万"}
    assert _extract_numbers("无数字") == set()


def test_extract_numbers_multiple_formats():
    # 整数 / 浮点 / 量级单位
    text = "上周帮客户 5 笔, 总额 30 万 USDT, 单笔 50k"
    nums = _extract_numbers(text)
    assert "5" in nums
    assert "30" in nums or "30万" in nums
    assert "50k" in nums


def test_numeric_consistency_ok_when_all_numbers_in_sources():
    reply = "USDT 大额 T+0 直接到账, 上周帮客户跑了 100k 单笔"
    sources = ["案例: 100k USDT 单笔, 3 天到账", "KB: T+0 结算"]
    assert _numeric_consistency_ok(reply, sources) is True


def test_numeric_consistency_blocks_hallucinated_number():
    reply = "USDT 大额. 上周帮客户跑了 999k"
    sources = ["案例: 100k USDT, 3 天"]
    assert _numeric_consistency_ok(reply, sources) is False


def test_numeric_consistency_ok_when_no_numbers():
    reply = "USDT 私聊详谈"
    sources = ["案例"]
    assert _numeric_consistency_ok(reply, sources) is True


@pytest.mark.asyncio
async def test_compose_phase2a_uses_case_top1_in_prompt():
    """compose 时 case_top1 应被拼进 prompt"""
    fake_case = MagicMock(
        problem="海外汇款", solution="USDT 场外", outcome="3 天到账",
        deal_size="100k USDT",
    )
    captured_prompt = {}

    async def fake_llm_generate(prompt):
        captured_prompt["v"] = prompt
        return "USDT 大额 T+0 100k 案例已成 私聊"

    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT T+0", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.find_case_top_k",
        return_value=[fake_case],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(side_effect=fake_llm_generate),
    ):
        result = await compose_reply_phase2a(
            customer_id=1,
            source_text="想买 100k USDT",
            solution_topic="USDT 大额场外",
            session=MagicMock(),
        )
    assert result is not None
    prompt = captured_prompt["v"]
    assert "100k USDT" in prompt  # case deal_size
    assert "海外汇款" in prompt  # case problem
    assert "3 天到账" in prompt  # case outcome


@pytest.mark.asyncio
async def test_compose_phase2a_numeric_filter_rejects_hallucinated_reply():
    """LLM 吐出 case 没有的数字 → 反幻觉拒, 重试"""
    fake_case = MagicMock(
        problem="x", solution="x", outcome="x", deal_size="100k USDT",
    )
    bad_reply = "USDT 大额. 帮客户跑了 999k"  # 999k 不在源数据里
    good_reply = "USDT 大额 100k 案例已成 私聊"

    call_count = {"n": 0}
    async def fake_llm(prompt):
        call_count["n"] += 1
        return bad_reply if call_count["n"] == 1 else good_reply

    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.reply_composer.find_case_top_k",
        return_value=[fake_case],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(side_effect=fake_llm),
    ):
        result = await compose_reply_phase2a(
            customer_id=1, source_text="x", solution_topic="USDT 大额",
            session=MagicMock(),
        )
    assert result == good_reply or "100k" in result
    assert call_count["n"] >= 2  # 第一次被拒, 重试


@pytest.mark.asyncio
async def test_compose_phase2a_no_case_fallback_to_kb_only():
    """无案例匹配 → 用 KB 兜底, 不要因为案例缺失就失败"""
    with patch(
        "app.services.reply_composer.kb_retrieve_top_k",
        new=AsyncMock(return_value=[{"text": "USDT T+0", "score": 0.9}]),
    ), patch(
        "app.services.reply_composer.find_case_top_k", return_value=[],
    ), patch(
        "app.services.reply_composer.llm_generate_reply",
        new=AsyncMock(return_value="USDT T+0 直接到账 私聊"),
    ):
        result = await compose_reply_phase2a(
            customer_id=1, source_text="x", solution_topic="USDT",
            session=MagicMock(),
        )
    assert result is not None
