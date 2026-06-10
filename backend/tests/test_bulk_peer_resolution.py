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


from app.services.telegram_client import resolve_and_send_with_client


def test_username_send_success():
    async def fake_run(account, op, *a, **kw):
        client = MagicMock()
        client.send_chat_action = AsyncMock()
        client.send_message = AsyncMock()
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username="bob", phone=None,
            message="hi", db_session=None))
    assert ok is True and err is None


def test_username_not_occupied_is_permanent():
    async def fake_run(account, op, *a, **kw):
        client = MagicMock()
        client.send_chat_action = AsyncMock()
        client.send_message = AsyncMock(side_effect=Exception("[400 USERNAME_NOT_OCCUPIED]"))
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username="ghost", phone=None,
            message="hi", db_session=None))
    assert ok is False and err == "perm:username_not_occupied"


def _client_with_imported(users):
    client = MagicMock()
    client.send_chat_action = AsyncMock()
    client.send_message = AsyncMock()
    client.delete_contacts = AsyncMock()
    imported = MagicMock()
    imported.users = users
    client.import_contacts = AsyncMock(return_value=imported)
    return client


def test_phone_hit_sends_and_cleans_contact():
    user = MagicMock(); user.id = 555
    client = _client_with_imported([user])
    async def fake_run(account, op, *a, **kw):
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username=None, phone="+15551234567",
            message="hi", db_session=None))
    assert ok is True and err is None
    client.send_message.assert_awaited_once_with(555, "hi")
    client.delete_contacts.assert_awaited_once_with([555])


def test_phone_not_on_telegram_is_permanent():
    client = _client_with_imported([])
    async def fake_run(account, op, *a, **kw):
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username=None, phone="+15550000000",
            message="hi", db_session=None))
    assert ok is False and err == "perm:phone_not_on_telegram"


def test_phone_send_failure_still_cleans_contact():
    user = MagicMock(); user.id = 777
    client = _client_with_imported([user])
    client.send_message = AsyncMock(side_effect=Exception("USER_PRIVACY_RESTRICTED"))
    async def fake_run(account, op, *a, **kw):
        return (True, await op(client))
    with patch("app.services.telegram_client._create_client_and_run", side_effect=fake_run):
        ok, err = asyncio.run(resolve_and_send_with_client(
            MagicMock(), tg_user_id=None, tg_username=None, phone="+15557654321",
            message="hi", db_session=None))
    assert ok is False and err == "perm:privacy_restricted"
    client.delete_contacts.assert_awaited_once_with([777])


from app.tasks.bulk_send_tasks import _do_send
from app.models.bulk_send import BulkTarget, BulkTemplateVariant


def test_do_send_prefers_username_over_userid(monkeypatch):
    captured = {}

    async def fake_resolve(account, *, tg_user_id, tg_username, phone, message, db_session):
        captured.update(tg_user_id=tg_user_id, tg_username=tg_username, phone=phone)
        return True, None

    monkeypatch.setattr(
        "app.services.telegram_client.resolve_and_send_with_client", fake_resolve
    )
    fake_session = MagicMock()
    fake_session.get.return_value = MagicMock()  # account
    target = BulkTarget(batch_id=1, customer_id=1, tg_user_id=999, tg_username="bob")
    variant = BulkTemplateVariant(batch_id=1, content="hi")
    ok, err = _do_send(fake_session, account_id=5, target=target, variant=variant, mock=False)
    assert ok is True and err is None
    assert captured["tg_username"] == "bob" and captured["tg_user_id"] == 999


def test_do_send_passes_perm_error_through(monkeypatch):
    async def fake_resolve(account, **kw):
        return False, "perm:privacy_restricted"
    monkeypatch.setattr(
        "app.services.telegram_client.resolve_and_send_with_client", fake_resolve
    )
    fake_session = MagicMock()
    fake_session.get.return_value = MagicMock()
    target = BulkTarget(batch_id=1, customer_id=1, tg_username="bob")
    variant = BulkTemplateVariant(batch_id=1, content="hi")
    ok, err = _do_send(fake_session, account_id=5, target=target, variant=variant, mock=False)
    assert ok is False and err == "perm:privacy_restricted"
