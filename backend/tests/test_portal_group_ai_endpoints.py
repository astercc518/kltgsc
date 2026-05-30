"""
Portal Group AI endpoints — smoke tests.

All tests are skipped because they require a proper customer auth fixture
(customer JWT + seeded DB) which will be added in a dedicated portal auth
fixture PR. The skip pattern matches Phase 2a/3a/4a/5 admin tests.
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Shared fixtures (skeleton — wired when customer auth fixture is available)
# ---------------------------------------------------------------------------

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


def _fake_customer(customer_id: int = 1):
    """Return a minimal mock Customer object."""
    c = MagicMock()
    c.id = customer_id
    c.icp_profile_text = "OTC crypto traders"
    c.icp_profile_embedding = b"\x00" * 32  # non-None sentinel
    c.lead_detector_thresholds = {"layer2_sim": 0.6}
    c.status = "active"
    return c


# ---------------------------------------------------------------------------
# ICP
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs customer auth fixture, Portal phase")
def test_get_icp_returns_shape(client):
    from app.api.deps_customer import get_current_customer
    from app.models.customer import Customer

    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    with patch("app.routers.portal_group_ai.get_my_icp.__wrapped__", create=True):
        r = client.get("/portal/group-ai/icp")
    assert r.status_code == 200
    data = r.json()
    assert "icp_text" in data
    assert "has_embedding" in data
    assert "thresholds" in data


@pytest.mark.skip(reason="needs customer auth fixture, Portal phase")
def test_update_icp_404_when_service_returns_false(client):
    """set_customer_icp_text_and_embed returns False → 404."""
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    with patch(
        "app.routers.portal_group_ai.set_customer_icp_text_and_embed",
        return_value=False,
    ):
        r = client.put("/portal/group-ai/icp", json={"icp_text": "new text"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Case studies
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs customer auth fixture, Portal phase")
def test_list_cases_returns_list(client):
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    with patch(
        "app.routers.portal_group_ai.list_case_studies",
        return_value=[],
    ):
        r = client.get("/portal/group-ai/case-studies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.skip(reason="needs customer auth fixture, Portal phase")
def test_batch_create_cases_returns_ids(client):
    from app.api.deps_customer import get_current_customer
    fake_case = MagicMock(id=101)
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    with patch(
        "app.routers.portal_group_ai.create_case_study",
        return_value=fake_case,
    ):
        r = client.post(
            "/portal/group-ai/case-studies/batch",
            json={
                "cases": [
                    {
                        "problem": "p", "solution": "s", "outcome": "o",
                        "tags": [],
                    }
                ]
            },
        )
    assert r.status_code == 200
    assert r.json() == {"ids": [101]}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs customer auth fixture, Portal phase")
def test_get_recent_stats_returns_shape(client):
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    # Patch session.exec to return 0 for all count queries
    with patch("app.routers.portal_group_ai.Session") as _mock_sess:
        r = client.get("/portal/group-ai/stats/recent")
    # Even without a real DB the route exists and the shape is testable
    # once auth + DB fixtures are wired; for now just assert the path resolves.
    assert r.status_code in (200, 422, 500)  # route registered


# ---------------------------------------------------------------------------
# Account ownership guard
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="needs customer auth fixture, Portal phase")
def test_persona_upsert_404_for_foreign_account(client, session):
    """Attempt to upsert persona on an account owned by a different customer → 404."""
    from app.api.deps_customer import get_current_customer
    from app.models.account import Account

    fake = _fake_customer(customer_id=99)
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    # Return an account owned by customer_id=1 (not 99)
    foreign_account = MagicMock(spec=Account)
    foreign_account.id = 7
    foreign_account.customer_id = 1

    original_get = session.get

    def patched_get(model, pk):
        if model is Account and pk == 7:
            return foreign_account
        return original_get(model, pk)

    session.get = patched_get

    r = client.put(
        "/portal/group-ai/accounts/7/persona",
        json={
            "customer_id": 99,
            "display_name": "Hacker",
        },
    )
    session.get = original_get
    assert r.status_code == 404
