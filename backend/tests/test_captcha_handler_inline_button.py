"""Tests for inline_button captcha handler."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.captcha_handlers.inline_button import solve_inline_button


@pytest.mark.asyncio
async def test_clicks_verify_button():
    """solve_inline_button finds and clicks a verify keyword button."""
    fake_btn = MagicMock(text="I am human")
    fake_btn.click = AsyncMock()
    fake_msg = MagicMock(
        reply_markup=MagicMock(),
        buttons=[[fake_btn]],
    )
    result = await solve_inline_button(telethon_client=None, message=fake_msg)
    assert result["success"] is True
    assert result["clicked_button"] == "I am human"
    assert result["error"] is None
    fake_btn.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_dry_run_no_click():
    """dry_run=True returns success but does not actually click."""
    fake_btn = MagicMock(text="Verify")
    fake_btn.click = AsyncMock()
    fake_msg = MagicMock(reply_markup=MagicMock(), buttons=[[fake_btn]])
    result = await solve_inline_button(telethon_client=None, message=fake_msg, dry_run=True)
    assert result["success"] is True
    assert result["clicked_button"] == "Verify"
    fake_btn.click.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_keyboard_returns_error():
    """Message with no reply_markup returns no_keyboard error."""
    fake_msg = MagicMock(reply_markup=None, buttons=[])
    result = await solve_inline_button(telethon_client=None, message=fake_msg)
    assert result["success"] is False
    assert result["error"] == "no_keyboard"


@pytest.mark.asyncio
async def test_no_verify_button_found():
    """Message with buttons but none matching keywords returns no_verify_button_found."""
    fake_btn = MagicMock(text="Cancel")
    fake_btn.click = AsyncMock()
    fake_msg = MagicMock(reply_markup=MagicMock(), buttons=[[fake_btn]])
    result = await solve_inline_button(telethon_client=None, message=fake_msg)
    assert result["success"] is False
    assert result["error"] == "no_verify_button_found"
    fake_btn.click.assert_not_awaited()
