"""Customer-facing redeem-code endpoint."""
import pytest
from sqlmodel import select

from app.models.activation_code import CODE_REDEEMED
from app.models.subscription import Subscription, SUB_ACTIVE


@pytest.fixture
def customer_user(session):
    from app.models.customer import Customer
    c = Customer(
        email="cust@t.t", hashed_password="x", status="pending",
        plan=None, account_quota=0, group_quota=0, token_quota=0, seat_quota=0,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@pytest.fixture
def customer_client(client, customer_user):
    from app.main import app
    from app.api.deps_customer import get_current_customer

    app.dependency_overrides[get_current_customer] = lambda: customer_user
    yield client, customer_user
    app.dependency_overrides.pop(get_current_customer, None)


def test_redeem_endpoint_creates_active_subscription(
    customer_client, session, monkeypatch,
):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    client, customer = customer_client
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="growth", count=1)

    resp = client.post(
        "/api/v1/customer/redeem-code",
        json={"code": code.code},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["plan"] == "growth"
    assert body["activated_via"] == "code"


def test_redeem_endpoint_unknown_code_returns_404(customer_client):
    client, _ = customer_client
    resp = client.post(
        "/api/v1/customer/redeem-code",
        json={"code": "NOTEXIST0001"},
    )
    assert resp.status_code == 404


def test_redeem_endpoint_already_used_returns_409(
    customer_client, session, monkeypatch,
):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    client, _ = customer_client
    from app.services.activation_code_service import generate_codes
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    client.post("/api/v1/customer/redeem-code", json={"code": code.code})
    resp = client.post("/api/v1/customer/redeem-code", json={"code": code.code})
    assert resp.status_code == 409


def test_redeem_endpoint_invalid_format_returns_400(customer_client):
    client, _ = customer_client
    resp = client.post(
        "/api/v1/customer/redeem-code",
        json={"code": "tooshort"},
    )
    assert resp.status_code == 400
