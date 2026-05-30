"""Tests for gemini_vision_adapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


@pytest.mark.asyncio
async def test_no_key_returns_none(monkeypatch):
    """analyze_captcha_image returns None when no API key is configured."""
    import app.services.gemini_vision_adapter as module

    monkeypatch.delenv("GEMINI_VISION_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = await module.analyze_captcha_image(image_bytes=b"\x89PNG", prompt_hint="选汽车")
    assert result is None


@pytest.mark.asyncio
async def test_successful_api_returns_parsed_text(monkeypatch):
    """analyze_captcha_image returns the text from a successful Gemini response."""
    import app.services.gemini_vision_adapter as module

    monkeypatch.setenv("GEMINI_VISION_API_KEY", "fake-key-123")

    fake_response_data = {
        "candidates": [{
            "content": {
                "parts": [{"text": "图片显示 6 个格子, 第 1,3,5 格是汽车"}]
            }
        }]
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=fake_response_data)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(module.httpx, "AsyncClient", return_value=mock_client):
        result = await module.analyze_captcha_image(
            image_bytes=b"\x89PNG\r\n\x1a\n", prompt_hint="请选择所有汽车"
        )

    assert result == "图片显示 6 个格子, 第 1,3,5 格是汽车"


@pytest.mark.asyncio
async def test_api_error_returns_none(monkeypatch):
    """analyze_captcha_image returns None when httpx raises an exception."""
    import app.services.gemini_vision_adapter as module

    monkeypatch.setenv("GEMINI_VISION_API_KEY", "fake-key-123")

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(module.httpx, "AsyncClient", return_value=mock_client):
        result = await module.analyze_captcha_image(image_bytes=b"\x89PNG", prompt_hint="")

    assert result is None


@pytest.mark.asyncio
async def test_empty_candidates_returns_none(monkeypatch):
    """analyze_captcha_image returns None when API returns empty candidates."""
    import app.services.gemini_vision_adapter as module

    monkeypatch.setenv("GEMINI_VISION_API_KEY", "fake-key-123")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"candidates": []})

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(module.httpx, "AsyncClient", return_value=mock_client):
        result = await module.analyze_captcha_image(image_bytes=b"\x89PNG", prompt_hint="")

    assert result is None
