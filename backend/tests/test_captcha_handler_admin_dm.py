"""Tests for admin_dm captcha handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.captcha_handlers.admin_dm import solve_admin_dm


@pytest.mark.asyncio
async def test_no_template_returns_error():
    """No customer_intro_template returns no_template_set error."""
    result = await solve_admin_dm(
        telethon_client=None,
        admin_user_id=12345,
        customer_intro_template=None,
    )
    assert result["success"] is False
    assert result["error"] == "no_template_set"
    assert result["answer"] is None


@pytest.mark.asyncio
async def test_empty_template_returns_error():
    """Empty string template also returns no_template_set error."""
    result = await solve_admin_dm(
        telethon_client=None,
        admin_user_id=12345,
        customer_intro_template="",
    )
    assert result["success"] is False
    assert result["error"] == "no_template_set"


@pytest.mark.asyncio
async def test_sends_template_to_admin_successfully():
    """Sends template DM to admin and returns success."""
    fake_client = MagicMock()
    fake_client.send_message = AsyncMock()

    template = "你好, 看到xx推荐的, 想加群学习交流."
    result = await solve_admin_dm(
        telethon_client=fake_client,
        admin_user_id=99999,
        customer_intro_template=template,
    )

    assert result["success"] is True
    assert result["answer"] == template
    assert result["error"] is None
    fake_client.send_message.assert_awaited_once_with(99999, template)


@pytest.mark.asyncio
async def test_dry_run_does_not_send():
    """dry_run=True returns success without calling send_message."""
    fake_client = MagicMock()
    fake_client.send_message = AsyncMock()

    template = "你好, 想加群学习."
    result = await solve_admin_dm(
        telethon_client=fake_client,
        admin_user_id=88888,
        customer_intro_template=template,
        dry_run=True,
    )

    assert result["success"] is True
    assert result["answer"] == template
    fake_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_failure_returns_error():
    """Telethon exception causes success=False with error message."""
    fake_client = MagicMock()
    fake_client.send_message = AsyncMock(side_effect=Exception("FloodWaitError"))

    result = await solve_admin_dm(
        telethon_client=fake_client,
        admin_user_id=77777,
        customer_intro_template="你好, 想加入.",
    )

    assert result["success"] is False
    assert "FloodWaitError" in result["error"]
    assert result["answer"] is None
