"""LLMRouter selects Vertex for clean text, DeepSeek for grey, refuses on red."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from sqlmodel import Session

from app.services.safety.router import LLMRouter, RouteDecision
from app.services.safety.gate import SafetyVerdict
from app.services.safety.moderation import ModerationVerdict, ModerationScore


def _clean_verdict():
    return SafetyVerdict(
        blocked=False, block_layer=None,
        blacklist_list=None, blacklist_term=None,
        moderation=ModerationVerdict(
            score=ModerationScore(toxic=0.01),
            tier="clean", blocked=False, avoid_vertex=False, dim_triggered=None,
        ),
        avoid_vertex=False,
    )


def _grey_verdict():
    return SafetyVerdict(
        blocked=False, block_layer=None,
        blacklist_list=None, blacklist_term=None,
        moderation=ModerationVerdict(
            score=ModerationScore(toxic=0.6),
            tier="grey", blocked=False, avoid_vertex=True, dim_triggered="toxic",
        ),
        avoid_vertex=True,
    )


def _red_verdict():
    return SafetyVerdict(
        blocked=True, block_layer="L1",
        blacklist_list=None, blacklist_term=None,
        moderation=ModerationVerdict(
            score=ModerationScore(toxic=0.95),
            tier="red", blocked=True, avoid_vertex=True, dim_triggered="toxic",
        ),
        avoid_vertex=True,
    )


def test_decide_clean_picks_vertex():
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    d = router.decide(_clean_verdict())
    assert d.routed_to == "vertex"
    assert d.config_id == 1
    assert d.refuse is False


def test_decide_grey_picks_deepseek():
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    d = router.decide(_grey_verdict())
    assert d.routed_to == "deepseek"
    assert d.config_id == 2
    assert d.refuse is False


def test_decide_red_refuses():
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    d = router.decide(_red_verdict())
    assert d.refuse is True
    assert d.routed_to is None
    assert d.config_id is None


def test_decide_grey_without_deepseek_fails_closed():
    """Critical: when avoid_vertex=True but no DeepSeek config, refuse rather
    than fall back to Vertex. Failing closed is the whole point of the layer."""
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=None)
    d = router.decide(_grey_verdict())
    assert d.refuse is True
    assert "no DeepSeek" in d.reason


@pytest.mark.asyncio
async def test_generate_clean_text_calls_vertex_llmservice():
    mock_session = MagicMock(spec=Session)
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    with patch("app.services.safety.router._GATE.evaluate",
               return_value=_clean_verdict()), \
         patch("app.services.safety.router.LLMService") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.get_response = AsyncMock(return_value="ok")

        out = await router.generate(mock_session, "hello", source="t1")

        assert out == "ok"
        mock_llm_cls.assert_called_once()
        _, kwargs = mock_llm_cls.call_args
        assert kwargs.get("config_id") == 1

        # Verify source-suffix contract: downstream sees `t1:routed_vertex`
        mock_llm.get_response.assert_awaited_once()
        _, get_resp_kwargs = mock_llm.get_response.call_args
        assert get_resp_kwargs.get("source") == "t1:routed_vertex"


@pytest.mark.asyncio
async def test_generate_grey_text_calls_deepseek_with_correct_source():
    mock_session = MagicMock(spec=Session)
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    with patch("app.services.safety.router._GATE.evaluate",
               return_value=_grey_verdict()), \
         patch("app.services.safety.router.LLMService") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.get_response = AsyncMock(return_value="grey ok")

        out = await router.generate(mock_session, "borderline", source="t2")

        assert out == "grey ok"
        _, kwargs = mock_llm_cls.call_args
        assert kwargs.get("config_id") == 2  # deepseek
        _, get_resp_kwargs = mock_llm.get_response.call_args
        assert get_resp_kwargs.get("source") == "t2:routed_deepseek"


@pytest.mark.asyncio
async def test_generate_red_refuses_without_calling_provider():
    mock_session = MagicMock(spec=Session)
    router = LLMRouter(vertex_config_id=1, deepseek_config_id=2)
    with patch("app.services.safety.router._GATE.evaluate",
               return_value=_red_verdict()), \
         patch("app.services.safety.router.LLMService") as mock_llm_cls:
        out = await router.generate(mock_session, "explicit", source="t2")
    assert out is None
    mock_llm_cls.assert_not_called()
