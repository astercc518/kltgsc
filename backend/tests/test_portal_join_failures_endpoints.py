"""
portal_join_failures endpoints — smoke tests (Phase 8 Task 9).

All tests are skipped because they require a proper customer auth fixture
(customer JWT + seeded DB with join_attempt rows) which will be added in
a dedicated portal auth fixture PR. The skip pattern matches the
established Portal phase pattern (see test_portal_discovery_endpoints.py).
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
def test_list_join_failures_returns_list(client):
    """GET /portal/group-ai/join/failures returns a list for authenticated customer."""
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    r = client.get("/portal/group-ai/join/failures")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.skip(reason="needs customer auth fixture + seeded DB, Portal phase")
def test_abandon_join_attempt_404_when_not_found(client):
    """POST /portal/group-ai/join/999/abandon → 404 for non-existent attempt."""
    from app.api.deps_customer import get_current_customer
    fake = _fake_customer()
    client.app.dependency_overrides[get_current_customer] = lambda: fake

    r = client.post("/portal/group-ai/join/999/abandon")
    assert r.status_code == 404
