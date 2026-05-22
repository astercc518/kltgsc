"""Admin activation code API endpoints."""
import pytest
from sqlmodel import select

from app.models.activation_code import ActivationCode, CODE_UNUSED, CODE_REVOKED


@pytest.fixture
def admin_user(session):
    from app.core.security import get_password_hash
    from app.models.user import User
    u = User(username="admin_ac_test", hashed_password=get_password_hash("x"), is_superuser=True)
    session.add(u); session.commit(); session.refresh(u)
    return u


@pytest.fixture
def admin_client(client, session, admin_user):
    """TestClient with get_current_admin overridden to return the test admin user."""
    from app.main import app
    from app.api.deps import get_current_admin

    app.dependency_overrides[get_current_admin] = lambda: admin_user
    yield client
    # clean up override (client fixture already clears dependency_overrides on teardown,
    # but be explicit to avoid cross-test leakage)
    app.dependency_overrides.pop(get_current_admin, None)


def test_generate_codes_endpoint(admin_client, session):
    resp = admin_client.post(
        "/api/v1/admin/billing/activation-codes/generate",
        json={"plan": "starter", "count": 5, "duration_days": 30, "notes": "test batch"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "batch_id" in body
    assert len(body["codes"]) == 5
    for c in body["codes"]:
        assert c["plan"] == "starter"
        assert c["status"] == "unused"
        assert len(c["code"]) == 12


def test_generate_codes_invalid_plan_returns_400(admin_client):
    resp = admin_client.post(
        "/api/v1/admin/billing/activation-codes/generate",
        json={"plan": "freemium", "count": 1},
    )
    assert resp.status_code == 400


def test_generate_codes_invalid_count_returns_422(admin_client):
    resp = admin_client.post(
        "/api/v1/admin/billing/activation-codes/generate",
        json={"plan": "starter", "count": 1000},  # > max 500
    )
    assert resp.status_code in (400, 422)


def test_list_codes(admin_client, session):
    from app.services.activation_code_service import generate_codes
    generate_codes(session, admin_user_id=1, plan="starter", count=3)
    generate_codes(session, admin_user_id=1, plan="growth", count=2)

    resp = admin_client.get("/api/v1/admin/billing/activation-codes")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list) or "items" in body
    items = body if isinstance(body, list) else body["items"]
    assert len(items) >= 5


def test_list_codes_filter_by_plan(admin_client, session):
    from app.services.activation_code_service import generate_codes
    generate_codes(session, admin_user_id=1, plan="starter", count=2)
    generate_codes(session, admin_user_id=1, plan="growth", count=3)
    resp = admin_client.get("/api/v1/admin/billing/activation-codes?plan=growth")
    assert resp.status_code == 200
    items = resp.json() if isinstance(resp.json(), list) else resp.json()["items"]
    assert all(c["plan"] == "growth" for c in items)


def test_get_code_detail(admin_client, session):
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="pro", count=1)
    resp = admin_client.get(f"/api/v1/admin/billing/activation-codes/{code.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == code.id
    assert body["code"] == code.code


def test_revoke_code_endpoint(admin_client, session):
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    resp = admin_client.post(f"/api/v1/admin/billing/activation-codes/{code.id}/revoke")
    assert resp.status_code == 200
    session.refresh(code)
    assert code.status == CODE_REVOKED
