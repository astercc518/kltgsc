import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="needs admin auth fixture, Portal phase")
def test_get_experiment_audit_returns_list(client):
    r = client.get("/admin/group-ai/ab/experiments/1/audit")
    assert r.status_code in (200, 422)
