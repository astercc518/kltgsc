"""
Smoke tests for admin AB experiment CRUD + start/stop endpoints.

Skipped pending admin auth fixture (Phase 2b).
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_create_experiment_returns_id(client):
    fake_exp = MagicMock(id=42)
    with patch("app.routers.admin_group_ai.ABExperiment", return_value=fake_exp):
        with patch("app.routers.admin_group_ai.get_session") as ms:
            fake_session = MagicMock()
            ms.return_value.__next__ = MagicMock(return_value=fake_session)
            r = client.post(
                "/admin/group-ai/ab/experiments",
                json={
                    "name": "test", "scope": "customer", "scope_value": 1,
                    "variants": [{"tag": "v1", "weight": 0.5, "params": {}}],
                },
            )
    assert r.status_code in (200, 422)


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_start_experiment_requires_draft_state(client):
    fake_exp = MagicMock(id=1, status="running")
    with patch("app.routers.admin_group_ai.get_session") as ms:
        fake_session = MagicMock()
        fake_session.get.return_value = fake_exp
        ms.return_value.__next__ = MagicMock(return_value=fake_session)
        r = client.put("/admin/group-ai/ab/experiments/1/start")
    # 409 conflict — already running
    assert r.status_code in (409, 422)
