import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.telegram_client import _perm_code


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """让 _send_with_typing 的拟人化延迟在测试中瞬时完成。"""
    monkeypatch.setattr("app.services.telegram_client.random.uniform", lambda a, b: 0)
    async def _instant(*a, **kw):
        return None
    monkeypatch.setattr("app.services.telegram_client.asyncio.sleep", _instant)


def test_perm_code_maps_permanent_errors():
    assert _perm_code("Telegram says: [400 USERNAME_NOT_OCCUPIED]") == "username_not_occupied"
    assert _perm_code("USERNAME_INVALID") == "username_invalid"
    assert _perm_code("[400 PEER_ID_INVALID]") == "peer_id_invalid"
    assert _perm_code("USER_PRIVACY_RESTRICTED") == "privacy_restricted"
    assert _perm_code("PRIVACY_RESTRICTED whatever") == "privacy_restricted"


def test_perm_code_returns_none_for_transient():
    assert _perm_code("FLOOD_WAIT_X 30") is None
    assert _perm_code("Connection refused") is None
    assert _perm_code("PEER_FLOOD") is None
    assert _perm_code("") is None
