"""Inbox API: list / approve / edit suggested replies"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_list_returns_sent_and_suggested(client):
    fake_rows = [
        MagicMock(
            id=1, status="sent", reply_text="USDT 大额", chat_id=-100,
            source_user_id=999, sent_at=None, decided_at=None,
            layer3_solution_topic="USDT", layer3_needs=["100k"],
        ),
        MagicMock(
            id=2, status="suggested", reply_text="[AI 草稿失败]", chat_id=-100,
            source_user_id=999, sent_at=None, decided_at=None,
            layer3_solution_topic="USDT", layer3_needs=[],
        ),
    ]
    with patch(
        "app.routers.inbox_group_ai._fetch_inbox_rows", return_value=fake_rows,
    ):
        r = client.get("/inbox/group-ai/customers/1/recent")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_approve_suggested_changes_status_to_sent(client):
    with patch(
        "app.routers.inbox_group_ai.approve_suggested_reply",
        new=AsyncMock(return_value={"ok": True, "pending_reply_id": 42}),
    ) as approve_mock:
        r = client.post("/inbox/group-ai/suggested/42/approve")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    approve_mock.assert_awaited_once()


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_edit_suggested_writes_new_reply_text(client):
    with patch(
        "app.routers.inbox_group_ai._update_suggested_reply_text",
        return_value=True,
    ):
        r = client.put(
            "/inbox/group-ai/suggested/42",
            json={"reply_text": "改过的草稿"},
        )
    assert r.status_code == 200


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_approve_404_when_not_suggested(client):
    """状态不是 suggested 时拒绝 approve"""
    with patch(
        "app.routers.inbox_group_ai.approve_suggested_reply",
        new=AsyncMock(side_effect=ValueError("not in suggested state")),
    ):
        r = client.post("/inbox/group-ai/suggested/42/approve")
    assert r.status_code == 409  # conflict
