"""TGStat adapter unit tests (mock httpx)"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.tgstat_adapter import search_groups_by_keyword


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_token(monkeypatch):
    monkeypatch.delenv("TGSTAT_API_TOKEN", raising=False)
    result = await search_groups_by_keyword(keyword="USDT")
    assert result == []


@pytest.mark.asyncio
async def test_search_parses_tgstat_response(monkeypatch):
    monkeypatch.setenv("TGSTAT_API_TOKEN", "fake")
    fake_response = {
        "status": "ok",
        "response": {
            "items": [
                {"id": 100, "username": "usdt_group",
                 "title": "USDT OTC", "participants_count": 5000,
                 "category": "Crypto"},
            ],
        },
    }
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=fake_response)
    mock_resp.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.tgstat_adapter.httpx.AsyncClient", return_value=mock_client):
        result = await search_groups_by_keyword(keyword="USDT")
    assert len(result) == 1
    assert result[0]["username"] == "usdt_group"
    assert result[0]["participants_count"] == 5000
    assert result[0]["link"] == "https://t.me/usdt_group"


@pytest.mark.asyncio
async def test_search_handles_api_failure(monkeypatch):
    monkeypatch.setenv("TGSTAT_API_TOKEN", "fake")
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=Exception("API down"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.tgstat_adapter.httpx.AsyncClient", return_value=mock_client):
        result = await search_groups_by_keyword(keyword="USDT")
    assert result == []
