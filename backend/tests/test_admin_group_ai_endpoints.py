"""admin Group AI endpoints smoke (FastAPI TestClient)"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(session):
    from app.main import app
    from app.core.db import get_session

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_update_icp_endpoint_404_unknown_customer(client):
    with patch(
        "app.routers.admin_group_ai.set_customer_icp_text_and_embed",
        return_value=False,
    ):
        r = client.put("/admin/group-ai/customers/9999/icp", json={"icp_text": "x"})
    assert r.status_code == 404


def test_update_thresholds_validates_range(client, session):
    """layer2_sim=2.0 超出 [0,1] 范围 → 400。
    通过 monkeypatching session.get 让 Customer 存在，跳过 DB 创建复杂度。
    """
    from app.models.customer import Customer
    fake_customer = MagicMock(spec=Customer)
    fake_customer.id = 1
    fake_customer.lead_detector_thresholds = {}

    original_get = session.get

    def patched_get(model, pk):
        if model is Customer and pk == 1:
            return fake_customer
        return original_get(model, pk)

    session.get = patched_get

    r = client.put(
        "/admin/group-ai/customers/1/thresholds",
        json={"layer2_sim": 2.0},
    )
    # Restore
    session.get = original_get

    assert r.status_code == 400


def test_create_case_returns_id(client):
    fake_case = MagicMock(id=42)
    with patch(
        "app.routers.admin_group_ai.create_case_study", return_value=fake_case,
    ):
        r = client.post(
            "/admin/group-ai/customers/1/case-studies",
            json={
                "industry": "OTC", "deal_size": "100k", "period": "3d",
                "problem": "x", "solution": "y", "outcome": "z", "tags": [],
            },
        )
    assert r.status_code == 200
    assert r.json() == {"id": 42}
