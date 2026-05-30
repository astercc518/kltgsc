"""Tests for text_qa captcha handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_empty_question_returns_error():
    """Empty question returns empty_question error without calling LLM."""
    from app.services.captcha_handlers.text_qa import solve_text_qa

    result = await solve_text_qa(
        telethon_client=None,
        chat_id=12345,
        question="",
        customer_join_template="朋友推荐",
    )
    assert result["success"] is False
    assert result["error"] == "empty_question"
    assert result["answer"] is None


@pytest.mark.asyncio
async def test_llm_generates_short_answer_and_sends(monkeypatch):
    """LLM generates a short answer and it is sent via telethon."""
    from app.services.captcha_handlers import text_qa as tq_module

    fake_answer = "朋友推荐过来的"

    # Mock LLMService.generate
    mock_llm_instance = MagicMock()
    mock_llm_instance.generate = AsyncMock(return_value=fake_answer)
    mock_llm_cls = MagicMock(return_value=mock_llm_instance)

    # Mock engine Session so no real DB needed
    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_ctx.__exit__ = MagicMock(return_value=False)

    fake_client = MagicMock()
    fake_client.send_message = AsyncMock()

    with patch.object(tq_module, "LLMService", mock_llm_cls), \
         patch.object(tq_module, "Session", return_value=mock_session_ctx):
        result = await tq_module.solve_text_qa(
            telethon_client=fake_client,
            chat_id=99999,
            question="你怎么知道这个群?",
            customer_join_template="看业内群友推荐",
        )

    assert result["success"] is True
    assert result["answer"] == fake_answer
    assert result["error"] is None
    fake_client.send_message.assert_awaited_once_with(99999, fake_answer)


@pytest.mark.asyncio
async def test_dry_run_does_not_send(monkeypatch):
    """dry_run=True returns placeholder without calling LLM or send_message."""
    from app.services.captcha_handlers import text_qa as tq_module

    mock_llm_instance = MagicMock()
    mock_llm_instance.generate = AsyncMock(return_value="should_not_be_called")
    mock_llm_cls = MagicMock(return_value=mock_llm_instance)

    fake_client = MagicMock()
    fake_client.send_message = AsyncMock()

    with patch.object(tq_module, "LLMService", mock_llm_cls):
        result = await tq_module.solve_text_qa(
            telethon_client=fake_client,
            chat_id=99999,
            question="你怎么知道这个群?",
            customer_join_template=None,
            dry_run=True,
        )

    assert result["success"] is True
    assert result["answer"] == "[dry_run placeholder]"
    assert result["error"] is None
    # LLM must NOT be called in dry_run
    mock_llm_instance.generate.assert_not_awaited()
    fake_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_bad_llm_response_returns_error(monkeypatch):
    """LLM returning None causes bad_llm_response error."""
    from app.services.captcha_handlers import text_qa as tq_module

    mock_llm_instance = MagicMock()
    mock_llm_instance.generate = AsyncMock(return_value=None)
    mock_llm_cls = MagicMock(return_value=mock_llm_instance)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__ = MagicMock(return_value=MagicMock())
    mock_session_ctx.__exit__ = MagicMock(return_value=False)

    with patch.object(tq_module, "LLMService", mock_llm_cls), \
         patch.object(tq_module, "Session", return_value=mock_session_ctx):
        result = await tq_module.solve_text_qa(
            telethon_client=None,
            chat_id=99999,
            question="你怎么知道这个群?",
            customer_join_template=None,
        )

    assert result["success"] is False
    assert result["error"] == "bad_llm_response"
