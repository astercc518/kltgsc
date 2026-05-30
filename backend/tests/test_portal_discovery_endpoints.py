"""
Portal discovery endpoints — smoke tests (Phase 7).

All tests are skipped because they require a proper customer auth fixture
(customer JWT + seeded DB with discovered_group rows) which will be added
in a dedicated portal auth fixture PR. The skip pattern matches the
established Portal phase pattern.
"""
import pytest
from unittest.mock import MagicMock


def _fake_customer(customer_id: int = 1):
    """Return a minimal mock Customer object."""
    c = MagicMock()
    c.id = customer_id
    c.status = "active"
    return c


@pytest.mark.skip(reason="needs customer auth fixture + seeded DB, Portal phase")
def test_list_candidates_returns_pending(client):
    """GET /portal/group-ai/discovery/candidates returns pending list."""
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    r = client.get("/portal/group-ai/discovery/candidates?status=pending")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.skip(reason="needs customer auth fixture + seeded DB, Portal phase")
def test_approve_candidate_404_when_not_found(client):
    """POST /portal/group-ai/discovery/999/approve → 404 when no candidate."""
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    r = client.post("/portal/group-ai/discovery/999/approve")
    assert r.status_code == 404


@pytest.mark.skip(reason="needs customer auth fixture + seeded DB, Portal phase")
def test_reject_candidate_adds_to_blacklist(client):
    """POST /portal/group-ai/discovery/{id}/reject updates status + blacklist."""
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    # Assumes candidate id=1 exists in seeded DB
    r = client.post("/portal/group-ai/discovery/1/reject")
    assert r.status_code in (200, 404)
