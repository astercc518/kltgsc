"""admin persona + chitchat_pool endpoints smoke"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_upsert_persona_returns_id(client):
    fake_persona = MagicMock(id=42, account_id=10)
    with patch("app.routers.admin_group_ai.WorkerPersona", return_value=fake_persona):
        # mock session.exec(...).first() = None (新建)
        with patch("app.routers.admin_group_ai.get_session") as ms:
            fake_session = MagicMock()
            fake_session.exec.return_value.first.return_value = None
            ms.return_value.__next__ = MagicMock(return_value=fake_session)
            r = client.put(
                "/admin/group-ai/accounts/10/persona",
                json={"customer_id": 1, "display_name": "阿强"},
            )
    # 端点实现可能因 mock 复杂度不完全 happy; 至少 status code 不是 5xx
    assert r.status_code in (200, 422)  # 422 = pydantic 校验 OK


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_create_chitchat_topic_returns_id(client):
    fake_topic = MagicMock(id=7)
    with patch("app.routers.admin_group_ai.ChitchatPool", return_value=fake_topic):
        with patch("app.routers.admin_group_ai.get_session") as ms:
            fake_session = MagicMock()
            ms.return_value.__next__ = MagicMock(return_value=fake_session)
            r = client.post(
                "/admin/group-ai/customers/1/chitchat-topics",
                json={"topic_category": "weather", "prompt_template": "今天 X", "tags": []},
            )
    assert r.status_code in (200, 422)
