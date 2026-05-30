"""compose_reply_phase3 = compose_reply_phase2a + persona_rewriter"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.reply_composer import compose_reply_phase3


@pytest.mark.asyncio
async def test_compose_phase3_calls_phase2a_then_persona_rewrite():
    fake_session = MagicMock()
    persona = {
        "speaking_style": "casual", "catchphrases": ["搞不好"],
        "display_name": "阿强",
    }
    with patch(
        "app.services.reply_composer.compose_reply_phase2a",
        new=AsyncMock(return_value="USDT 大额 T+0 100k 案例已成 私聊"),
    ) as phase2a_mock, patch(
        "app.services.reply_composer.apply_persona",
        return_value="USDT 大额 T+0 100k 案例已成 私聊咯",
    ) as rewriter_mock:
        result = await compose_reply_phase3(
            customer_id=1, source_text="求 USDT",
            solution_topic="USDT 大额", session=fake_session, persona=persona,
        )
    assert result == "USDT 大额 T+0 100k 案例已成 私聊咯"
    phase2a_mock.assert_awaited_once()
    rewriter_mock.assert_called_once()
    args, kwargs = rewriter_mock.call_args
    assert args[0] == "USDT 大额 T+0 100k 案例已成 私聊"
    assert args[1] == persona


@pytest.mark.asyncio
async def test_compose_phase3_returns_none_when_phase2a_fails():
    fake_session = MagicMock()
    with patch(
        "app.services.reply_composer.compose_reply_phase2a",
        new=AsyncMock(return_value=None),
    ):
        result = await compose_reply_phase3(
            customer_id=1, source_text="x", solution_topic="x",
            session=fake_session, persona={"speaking_style": "casual"},
        )
    assert result is None


@pytest.mark.asyncio
async def test_compose_phase3_persona_none_falls_back_to_phase2a():
    """persona=None → 跳过改写, 直接返 phase2a 结果"""
    fake_session = MagicMock()
    with patch(
        "app.services.reply_composer.compose_reply_phase2a",
        new=AsyncMock(return_value="原始回复"),
    ), patch(
        "app.services.reply_composer.apply_persona",
    ) as rewriter_mock:
        result = await compose_reply_phase3(
            customer_id=1, source_text="x", solution_topic="x",
            session=fake_session, persona=None,
        )
    assert result == "原始回复"
    rewriter_mock.assert_not_called()
