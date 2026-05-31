"""
Phase 12: vision_button_hybrid handler + detector classification + inline_button
preferred_text hint.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.captcha_detector import detect_captcha_type
from app.services.captcha_handlers.inline_button import (
    list_button_texts,
    solve_inline_button,
)
from app.services.captcha_handlers.vision_button_hybrid import (
    solve_vision_button_hybrid,
)


def _msg_with_buttons(button_labels, *, has_photo=True, from_bot=True):
    """Build a pyrogram-shaped MagicMock message with buttons + photo."""
    m = MagicMock()
    m.text = "What is 3+5?"
    m.caption = ""
    m.photo = MagicMock() if has_photo else None

    u = MagicMock()
    u.is_bot = from_bot
    u.id = 9999
    m.from_user = u

    chat = MagicMock()
    chat.id = -100_777_888
    m.chat = chat

    rm = MagicMock()
    rm.inline_keyboard = [[
        type("Btn", (), {"text": b})() for b in button_labels
    ]]
    m.reply_markup = rm
    return m


# ── detector classification ──────────────────────────────────────────────────


def test_detector_classifies_photo_plus_buttons_as_vision_with_buttons():
    msg = {
        "text": "answer", "buttons": ["7", "8", "9"],
        "has_photo": True, "from_bot": True,
    }
    result = detect_captcha_type(
        recent_messages=[msg], admin_dms_after_join=[],
    )
    assert result["type"] == "vision_with_buttons"


def test_detector_still_returns_inline_button_when_no_photo():
    msg = {
        "text": "verify human", "buttons": ["I am human"],
        "has_photo": False, "from_bot": True,
    }
    result = detect_captcha_type(
        recent_messages=[msg], admin_dms_after_join=[],
    )
    assert result["type"] == "inline_button"


def test_detector_still_returns_vision_when_photo_without_buttons():
    msg = {
        "text": "select cars", "buttons": [],
        "has_photo": True, "from_bot": True,
    }
    result = detect_captcha_type(
        recent_messages=[msg], admin_dms_after_join=[],
    )
    assert result["type"] == "vision"


# ── list_button_texts ────────────────────────────────────────────────────────


def test_list_button_texts_returns_labels_in_order():
    msg = _msg_with_buttons(["A", "B", "C"])
    assert list_button_texts(msg) == ["A", "B", "C"]


def test_list_button_texts_filters_empty_labels():
    msg = _msg_with_buttons(["X", "", "Y", "   "])
    assert list_button_texts(msg) == ["X", "Y"]


# ── inline_button preferred_text hint ────────────────────────────────────────


@pytest.mark.asyncio
async def test_inline_button_preferred_text_clicks_matching_button():
    msg = _msg_with_buttons(["7", "8", "9"])
    msg.click = AsyncMock(return_value=None)

    result = await solve_inline_button(
        client=MagicMock(), message=msg, preferred_text="8",
    )
    assert result["success"] is True
    assert result["clicked_button"] == "8"
    msg.click.assert_awaited_once_with("8")


@pytest.mark.asyncio
async def test_inline_button_preferred_text_falls_back_when_unmatched():
    """If preferred_text isn't a real button, the keyword scan still tries."""
    msg = _msg_with_buttons(["I am human", "Cancel"])
    msg.click = AsyncMock(return_value=None)

    result = await solve_inline_button(
        client=MagicMock(), message=msg, preferred_text="ZZZ",
    )
    assert result["success"] is True
    assert result["clicked_button"] == "I am human"
    msg.click.assert_awaited_once_with("I am human")


# ── vision_button_hybrid integration ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_calls_gemini_and_clicks_chosen_button(monkeypatch):
    msg = _msg_with_buttons(["7", "8", "9", "10"])
    msg.click = AsyncMock(return_value=None)

    client = MagicMock()
    client.download_media = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n\x00\x00")

    mock_analyse = AsyncMock(return_value="8")
    monkeypatch.setattr(
        "app.services.captcha_handlers.vision_button_hybrid"
        ".analyze_captcha_button_choice",
        mock_analyse,
    )

    result = await solve_vision_button_hybrid(client=client, message=msg)
    assert result["success"] is True
    assert result["clicked_button"] == "8"
    assert result["picked_via"] == "vision"
    mock_analyse.assert_awaited_once()
    msg.click.assert_awaited_once_with("8")


@pytest.mark.asyncio
async def test_hybrid_falls_back_when_vision_returns_none(monkeypatch):
    msg = _msg_with_buttons(["I am human"])
    msg.click = AsyncMock(return_value=None)

    client = MagicMock()
    client.download_media = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n\x00\x00")

    monkeypatch.setattr(
        "app.services.captcha_handlers.vision_button_hybrid"
        ".analyze_captcha_button_choice",
        AsyncMock(return_value=None),
    )

    result = await solve_vision_button_hybrid(client=client, message=msg)
    # keyword scan finds "I am human" by VERIFY_BUTTON_KEYWORDS
    assert result["success"] is True
    assert result["picked_via"] == "keyword_fallback"
    assert result["clicked_button"] == "I am human"


@pytest.mark.asyncio
async def test_hybrid_returns_failure_when_no_buttons():
    """Defensive: orchestrator shouldn't dispatch here without buttons, but
    if it does the handler reports it cleanly rather than crashing."""
    m = MagicMock()
    m.reply_markup = None
    m.buttons = None
    m.photo = MagicMock()

    result = await solve_vision_button_hybrid(client=MagicMock(), message=m)
    assert result["success"] is False
    assert result["error"] == "no_buttons_on_message"


@pytest.mark.asyncio
async def test_hybrid_dry_run_skips_vision_call(monkeypatch):
    msg = _msg_with_buttons(["I am human"])

    spy_analyse = AsyncMock(return_value="I am human")
    monkeypatch.setattr(
        "app.services.captcha_handlers.vision_button_hybrid"
        ".analyze_captcha_button_choice",
        spy_analyse,
    )

    result = await solve_vision_button_hybrid(
        client=MagicMock(), message=msg, dry_run=True,
    )
    # dry_run path skips vision, just dry-runs inline_button keyword scan
    spy_analyse.assert_not_awaited()
    assert result["success"] is True
    assert result["picked_via"] == "keyword_fallback"
