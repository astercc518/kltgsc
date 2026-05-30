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


# ── _detect_mime_type unit tests ──────────────────────────────────────────────

def test_detect_mime_type_jpeg():
    """JPEG header bytes are detected as image/jpeg."""
    from app.services.gemini_vision_adapter import _detect_mime_type
    assert _detect_mime_type(b'\xff\xd8\xff\xe0' + b'\x00' * 10) == "image/jpeg"


def test_detect_mime_type_png():
    """PNG header bytes are detected as image/png."""
    from app.services.gemini_vision_adapter import _detect_mime_type
    assert _detect_mime_type(b'\x89PNG\r\n\x1a\n' + b'\x00' * 10) == "image/png"


def test_detect_mime_type_gif():
    """GIF header bytes are detected as image/gif."""
    from app.services.gemini_vision_adapter import _detect_mime_type
    assert _detect_mime_type(b'GIF89a' + b'\x00' * 10) == "image/gif"


def test_detect_mime_type_unknown_defaults_to_png():
    """Unknown bytes default to image/png."""
    from app.services.gemini_vision_adapter import _detect_mime_type
    assert _detect_mime_type(b'\x00\x01\x02\x03') == "image/png"


@pytest.mark.asyncio
async def test_jpeg_image_uses_jpeg_mime(monkeypatch):
    """analyze_captcha_image sends image/jpeg mime_type for JPEG bytes."""
    import app.services.gemini_vision_adapter as module

    monkeypatch.setenv("GEMINI_VISION_API_KEY", "fake-key-123")

    fake_response_data = {
        "candidates": [{"content": {"parts": [{"text": "captcha description"}]}}]
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=fake_response_data)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100

    with patch.object(module.httpx, "AsyncClient", return_value=mock_client):
        result = await module.analyze_captcha_image(
            image_bytes=jpeg_bytes, prompt_hint="test"
        )

    assert result == "captcha description"
    # Verify the mime_type sent to Gemini was image/jpeg
    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    inline_data = body["contents"][0]["parts"][1]["inline_data"]
    assert inline_data["mime_type"] == "image/jpeg"
