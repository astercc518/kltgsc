"""t.me/s public page adapter unit tests (mock httpx)"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.tme_search_adapter import fetch_group_info_by_username


@pytest.mark.asyncio
async def test_fetch_returns_none_for_empty():
    result = await fetch_group_info_by_username("")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_parses_og_tags():
    fake_html = """
    <html>
    <meta property="og:title" content="USDT OTC Group" />
    <meta property="og:description" content="买卖 USDT 大额场外" />
    <span>5,000 subscribers</span>
    </html>
    """
    mock_client = MagicMock()
    mock_resp = MagicMock(status_code=200, text=fake_html)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.tme_search_adapter.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_group_info_by_username("usdt_otc")
    assert result is not None
    assert result["title"] == "USDT OTC Group"
    assert result["members_count"] == 5000
