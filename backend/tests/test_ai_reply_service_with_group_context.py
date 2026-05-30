"""ai_reply_service: 私聊 LLM prompt 拼 group_reply_context"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ai_reply_service import generate_private_reply_with_context


@pytest.mark.asyncio
async def test_private_reply_includes_group_context_when_user_has_history():
    """source_user 7d 内被群里 AI 回复过 → 拼进私聊 prompt"""
    fake_group_context = [{
        "reply_text": "USDT 大额 T+0 100k 私聊详谈",
        "extracted_needs": ["100k USDT 买入"],
        "solution_topic": "USDT 大额场外",
        "sent_at": "2026-05-29T10:00:00+00:00",
        "chat_id": -100,
    }]
    captured_prompt = {}

    async def fake_llm(prompt):
        captured_prompt["v"] = prompt
        return "好的, 100k 量级 OK 的"

    with patch(
        "app.services.ai_reply_service.fetch_recent_group_replies_for_user",
        return_value=fake_group_context,
    ), patch(
        "app.services.ai_reply_service.llm_generate",
        new=AsyncMock(side_effect=fake_llm),
    ):
        result = await generate_private_reply_with_context(
            session=MagicMock(), customer_id=1, source_user_id=999,
            private_message="你这边什么价",
        )
    assert result == "好的, 100k 量级 OK 的"
    prompt = captured_prompt["v"]
    assert "USDT 大额场外" in prompt or "100k" in prompt


@pytest.mark.asyncio
async def test_private_reply_skips_context_when_no_history():
    with patch(
        "app.services.ai_reply_service.fetch_recent_group_replies_for_user",
        return_value=[],
    ), patch(
        "app.services.ai_reply_service.llm_generate",
        new=AsyncMock(return_value="一般回复"),
    ):
        result = await generate_private_reply_with_context(
            session=MagicMock(), customer_id=1, source_user_id=999,
            private_message="你好",
        )
    assert result == "一般回复"


@pytest.mark.asyncio
async def test_private_reply_context_fetch_failure_does_not_block():
    """fetch 异常 → 退化到无 context, 不阻塞私聊回复"""
    with patch(
        "app.services.ai_reply_service.fetch_recent_group_replies_for_user",
        side_effect=Exception("DB hiccup"),
    ), patch(
        "app.services.ai_reply_service.llm_generate",
        new=AsyncMock(return_value="兜底回复"),
    ):
        result = await generate_private_reply_with_context(
            session=MagicMock(), customer_id=1, source_user_id=999,
            private_message="你好",
        )
    assert result == "兜底回复"
