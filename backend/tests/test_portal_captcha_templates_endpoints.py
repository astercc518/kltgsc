"""
Phase 10 portal captcha-templates endpoint tests.

Unlike earlier portal endpoint tests (which were skipped pending an auth
fixture), these exercise the GET/PUT round trip end-to-end by overriding
get_current_customer to return a real Customer row seeded into the in-memory
session.
"""
import pytest

from app.models.customer import Customer


def _seed_customer(session, **overrides) -> Customer:
    defaults = dict(
        email="phase10@example.test",
        hashed_password="x",
        status="active",
        plan="starter",
        account_quota=3,
        group_quota=500,
        token_quota=2_000_000,
        seat_quota=1,
    )
    defaults.update(overrides)
    c = Customer(**defaults)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _override_current_customer(client, customer: Customer) -> None:
    from app.api.deps_customer import get_current_customer
    client.app.dependency_overrides[get_current_customer] = lambda: customer


def test_get_returns_nulls_when_unset(client, session):
    customer = _seed_customer(session)
    _override_current_customer(client, customer)

    r = client.get("/portal/group-ai/captcha-templates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "captcha_join_template": None,
        "captcha_intro_template": None,
    }


def test_put_persists_both_templates(client, session):
    customer = _seed_customer(session)
    _override_current_customer(client, customer)

    payload = {
        "captcha_join_template": "  我是做加密 OTC 的，看到群友推荐  ",
        "captcha_intro_template": "你好，朋友介绍来的，想加进来跟同行交流，多谢。",
    }
    r = client.put("/portal/group-ai/captcha-templates", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    # leading/trailing whitespace stripped
    assert body["captcha_join_template"] == "我是做加密 OTC 的，看到群友推荐"
    assert body["captcha_intro_template"] == payload["captcha_intro_template"]

    # GET sees the persisted values
    r2 = client.get("/portal/group-ai/captcha-templates")
    assert r2.json() == body


def test_put_partial_only_touches_present_field(client, session):
    customer = _seed_customer(
        session,
        captcha_join_template="OLD JOIN",
        captcha_intro_template="OLD INTRO",
    )
    _override_current_customer(client, customer)

    r = client.put(
        "/portal/group-ai/captcha-templates",
        json={"captcha_join_template": "NEW JOIN"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["captcha_join_template"] == "NEW JOIN"
    assert body["captcha_intro_template"] == "OLD INTRO"  # untouched


def test_put_empty_string_clears_field(client, session):
    customer = _seed_customer(
        session, captcha_join_template="OLD", captcha_intro_template="OLD INTRO",
    )
    _override_current_customer(client, customer)

    r = client.put(
        "/portal/group-ai/captcha-templates",
        json={"captcha_join_template": ""},
    )
    assert r.status_code == 200, r.text
    assert r.json()["captcha_join_template"] is None
    assert r.json()["captcha_intro_template"] == "OLD INTRO"


def _error_body_contains(body: dict, needle: str) -> bool:
    """The backend reshapes HTTPException into {"message": ..., ...}.
    Match against either FastAPI's default 'detail' or the project's 'message'."""
    for k in ("detail", "message"):
        v = body.get(k)
        if isinstance(v, str) and needle in v:
            return True
    return False


def test_put_rejects_overlength_join(client, session):
    customer = _seed_customer(session)
    _override_current_customer(client, customer)

    r = client.put(
        "/portal/group-ai/captcha-templates",
        json={"captcha_join_template": "x" * 401},
    )
    assert r.status_code == 400
    assert _error_body_contains(r.json(), "captcha_join_template")


def test_put_rejects_overlength_intro(client, session):
    customer = _seed_customer(session)
    _override_current_customer(client, customer)

    r = client.put(
        "/portal/group-ai/captcha-templates",
        json={"captcha_intro_template": "y" * 601},
    )
    assert r.status_code == 400
    assert _error_body_contains(r.json(), "captcha_intro_template")
