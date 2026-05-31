"""
Phase 12: gemini_vision_adapter button-choice helper.

Tests cover:
- Missing API key → None (graceful)
- Empty button list → None
- Strict JSON model output → label match
- Code-fenced JSON model output → label match
- Free prose containing the label → label match
- Model output that doesn't mention any button → None
- HTTP failure → None
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _png_bytes() -> bytes:
    """Minimal valid PNG header + ~10 bytes garbage so mime detection picks PNG."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _stub_gemini_response(text: str) -> dict:
    return {
        "candidates": [{
            "content": {"parts": [{"text": text}]}
        }]
    }


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv("GEMINI_VISION_API_KEY", "fake_key")
    from app.services import gemini_vision_adapter as adp
    return adp


@pytest.mark.asyncio
async def test_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_VISION_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app.services.gemini_vision_adapter import analyze_captcha_button_choice
    result = await analyze_captcha_button_choice(
        image_bytes=_png_bytes(), button_texts=["A", "B"],
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_for_empty_buttons(adapter):
    result = await adapter.analyze_captcha_button_choice(
        image_bytes=_png_bytes(), button_texts=[],
    )
    assert result is None


@pytest.mark.asyncio
async def test_strict_json_response_resolves_label(adapter):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(
        return_value=_stub_gemini_response('{"button": "8"}'),
    )
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)

    with patch.object(adapter.httpx, "AsyncClient", return_value=client):
        result = await adapter.analyze_captcha_button_choice(
            image_bytes=_png_bytes(),
            button_texts=["7", "8", "9", "10"],
            prompt_hint="what is 3+5?",
        )
    assert result == "8"


@pytest.mark.asyncio
async def test_code_fenced_json_resolves_label(adapter):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=_stub_gemini_response(
        '```json\n{"button": "Yes"}\n```'
    ))
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)

    with patch.object(adapter.httpx, "AsyncClient", return_value=client):
        result = await adapter.analyze_captcha_button_choice(
            image_bytes=_png_bytes(),
            button_texts=["Yes", "No"],
        )
    assert result == "Yes"


@pytest.mark.asyncio
async def test_prose_with_label_falls_back_to_substring_match(adapter):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=_stub_gemini_response(
        "The image shows a math question 3+5. The correct button is 8."
    ))
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)

    with patch.object(adapter.httpx, "AsyncClient", return_value=client):
        result = await adapter.analyze_captcha_button_choice(
            image_bytes=_png_bytes(),
            button_texts=["7", "8", "9", "10"],
        )
    assert result == "8"


@pytest.mark.asyncio
async def test_returns_none_when_response_mentions_no_label(adapter):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=_stub_gemini_response(
        "Cannot determine the answer from the image."
    ))
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)

    with patch.object(adapter.httpx, "AsyncClient", return_value=client):
        result = await adapter.analyze_captcha_button_choice(
            image_bytes=_png_bytes(),
            button_texts=["A", "B", "C"],
        )
    assert result is None


@pytest.mark.asyncio
async def test_http_error_returns_none(adapter):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))

    with patch.object(adapter.httpx, "AsyncClient", return_value=client):
        result = await adapter.analyze_captcha_button_choice(
            image_bytes=_png_bytes(),
            button_texts=["A", "B"],
        )
    assert result is None
