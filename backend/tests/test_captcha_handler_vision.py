"""Tests for vision captcha handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_no_photo_returns_error():
    """Message with no photo returns no_photo error."""
    from app.services.captcha_handlers.vision import solve_vision

    fake_msg = MagicMock(photo=None, text="select the cars")
    result = await solve_vision(telethon_client=None, message=fake_msg)
    assert result["success"] is False
    assert result["error"] == "no_photo"
    assert result["analysis"] is None


@pytest.mark.asyncio
async def test_vision_api_failure_returns_error():
    """When Gemini Vision returns None, handler returns vision_api_failed."""
    from app.services.captcha_handlers import vision as vision_module

    fake_client = MagicMock()
    fake_client.download_media = AsyncMock(return_value=b"\x89PNG\r\n")
    fake_msg = MagicMock(photo=MagicMock(), text="请选择所有汽车")

    with patch.object(vision_module, "analyze_captcha_image", AsyncMock(return_value=None)):
        result = await vision_module.solve_vision(telethon_client=fake_client, message=fake_msg)

    assert result["success"] is False
    assert result["error"] == "vision_api_failed"


@pytest.mark.asyncio
async def test_vision_returns_manual_review_needed():
    """Successful vision analysis returns success=False with manual_review_needed action."""
    from app.services.captcha_handlers import vision as vision_module

    analysis_text = "图片显示 6 个格子, 第 1,3 格是汽车"
    fake_client = MagicMock()
    fake_client.download_media = AsyncMock(return_value=b"\x89PNG\r\n")
    fake_msg = MagicMock(photo=MagicMock(), text="请选择所有汽车")

    with patch.object(vision_module, "analyze_captcha_image", AsyncMock(return_value=analysis_text)):
        result = await vision_module.solve_vision(telethon_client=fake_client, message=fake_msg)

    # Phase 8: success=False, manual_review_needed
    assert result["success"] is False
    assert result["analysis"] == analysis_text
    assert result["action_taken"] == "manual_review_needed"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_vision_dry_run_returns_success_true():
    """dry_run=True with successful analysis returns success=True."""
    from app.services.captcha_handlers import vision as vision_module

    analysis_text = "图片: 数字验证码 4829"
    fake_client = MagicMock()
    fake_client.download_media = AsyncMock(return_value=b"\x89PNG\r\n")
    fake_msg = MagicMock(photo=MagicMock(), text="输入验证码")

    with patch.object(vision_module, "analyze_captcha_image", AsyncMock(return_value=analysis_text)):
        result = await vision_module.solve_vision(
            telethon_client=fake_client, message=fake_msg, dry_run=True
        )

    assert result["success"] is True
    assert result["analysis"] == analysis_text
    assert result["action_taken"] is None
