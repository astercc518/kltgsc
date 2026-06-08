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


from app.services.telegram_client import _send_with_typing


def test_send_with_typing_calls_send_message():
    client = MagicMock()
    client.send_chat_action = AsyncMock()
    client.send_message = AsyncMock()
    asyncio.run(_send_with_typing(client, "@bob", "hi", min_pre=0, max_pre=0, min_type=0, max_type=0))
    client.send_message.assert_awaited_once_with("@bob", "hi")


def test_send_with_typing_survives_typing_action_failure():
    client = MagicMock()
    client.send_chat_action = AsyncMock(side_effect=Exception("typing blocked"))
    client.send_message = AsyncMock()
    asyncio.run(_send_with_typing(client, 123, "hi", min_pre=0, max_pre=0, min_type=0, max_type=0))
    client.send_message.assert_awaited_once_with(123, "hi")
