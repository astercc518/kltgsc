"""ActivationCodeService — generate/redeem/revoke unit tests."""
import re
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models.activation_code import (
    ActivationCode,
    CODE_UNUSED,
    CODE_REDEEMED,
    CODE_REVOKED,
)
from app.models.customer import Customer, STATUS_ACTIVE
from app.models.subscription import Subscription, SUB_ACTIVE
from app.services.activation_code_service import (
    ActivationCodeError,
    generate_codes,
    redeem_code,
    revoke_code,
)


# ── generate_codes ─────────────────────────────────────────────────────

def test_generate_codes_returns_requested_count(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=5)
    assert len(codes) == 5
    for c in codes:
        assert c.status == CODE_UNUSED
        assert c.plan == "starter"
        assert c.duration_days == 30
        assert re.fullmatch(r"[A-Z0-9]{12}", c.code), f"bad code format: {c.code}"


def test_generate_codes_assigns_same_batch_id(session):
    codes = generate_codes(session, admin_user_id=1, plan="growth", count=3)
    batch_ids = {c.batch_id for c in codes}
    assert len(batch_ids) == 1


def test_generate_codes_different_calls_get_different_batches(session):
    a = generate_codes(session, admin_user_id=1, plan="starter", count=2)
    b = generate_codes(session, admin_user_id=1, plan="starter", count=2)
    assert a[0].batch_id != b[0].batch_id


def test_generate_codes_rejects_invalid_plan(session):
    with pytest.raises(ActivationCodeError):
        generate_codes(session, admin_user_id=1, plan="freemium", count=1)


def test_generate_codes_persists_to_db(session):
    generate_codes(session, admin_user_id=1, plan="pro", count=4)
    rows = session.exec(select(ActivationCode).where(ActivationCode.plan == "pro")).all()
    assert len(rows) == 4


def test_generate_codes_codes_are_unique(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=20)
    seen = {c.code for c in codes}
    assert len(seen) == 20


def test_generate_codes_respects_duration_days(session):
    codes = generate_codes(session, admin_user_id=1, plan="starter", count=1, duration_days=90)
    assert codes[0].duration_days == 90


# ── redeem_code ────────────────────────────────────────────────────────

@pytest.fixture
def fresh_customer(session):
    c = Customer(
        email="redeem@t.t", hashed_password="x", status="pending",
        plan=None, account_quota=0, group_quota=0, token_quota=0, seat_quota=0,
    )
    session.add(c); session.commit(); session.refresh(c)
    return c


def test_redeem_unused_code_creates_active_subscription(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="growth", count=1)
    sub = redeem_code(session, fresh_customer, code.code)
    assert sub.status == SUB_ACTIVE
    assert sub.plan == "growth"
    assert sub.activated_via == "code"
    assert sub.activation_code_id == code.id


def test_redeem_marks_code_redeemed(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    redeem_code(session, fresh_customer, code.code)
    session.refresh(code)
    assert code.status == CODE_REDEEMED
    assert code.redeemed_by_customer_id == fresh_customer.id
    assert code.redeemed_subscription_id is not None
    assert code.redeemed_at is not None


def test_redeem_unknown_code_raises(session, fresh_customer):
    with pytest.raises(ActivationCodeError, match="not found"):
        redeem_code(session, fresh_customer, "NOTEXIST0001")


def test_redeem_already_redeemed_raises(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    redeem_code(session, fresh_customer, code.code)
    with pytest.raises(ActivationCodeError, match="already redeemed"):
        redeem_code(session, fresh_customer, code.code)


def test_redeem_revoked_code_raises(session, fresh_customer):
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    code.status = CODE_REVOKED
    session.add(code); session.commit()
    with pytest.raises(ActivationCodeError, match="revoked"):
        redeem_code(session, fresh_customer, code.code)


def test_redeem_case_insensitive_and_strips_dashes(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    # Convert to display form: "XXXX-XXXX-XXXX" with random casing
    formatted = f"{code.code[:4]}-{code.code[4:8]}-{code.code[8:]}".lower()
    sub = redeem_code(session, fresh_customer, formatted)
    assert sub.status == SUB_ACTIVE


def test_redeem_refreshes_customer_denormalized(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="pro", count=1)
    redeem_code(session, fresh_customer, code.code)
    session.refresh(fresh_customer)
    assert fresh_customer.plan == "pro"
    assert fresh_customer.subscription_status == SUB_ACTIVE
    assert fresh_customer.status == STATUS_ACTIVE


# ── revoke_code ────────────────────────────────────────────────────────

def test_revoke_unused_code_succeeds(session):
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    result = revoke_code(session, code.id, admin_user_id=1)
    assert result.status == CODE_REVOKED


def test_revoke_unknown_code_raises(session):
    with pytest.raises(ActivationCodeError, match="not found"):
        revoke_code(session, code_id=999999, admin_user_id=1)


def test_revoke_already_redeemed_raises(session, fresh_customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    redeem_code(session, fresh_customer, code.code)
    with pytest.raises(ActivationCodeError, match="already redeemed"):
        revoke_code(session, code.id, admin_user_id=1)


def test_revoke_already_revoked_is_idempotent(session):
    [code] = generate_codes(session, admin_user_id=1, plan="starter", count=1)
    revoke_code(session, code.id, admin_user_id=1)
    # Second revoke succeeds silently (idempotent)
    result = revoke_code(session, code.id, admin_user_id=1)
    assert result.status == CODE_REVOKED


# ── race-safety lock ───────────────────────────────────────────────────

def test_redeem_code_acquires_row_lock_on_select():
    """Verify redeem_code's ActivationCode SELECT opts into row locking.

    SQLite (test env) ignores the hint silently. PostgreSQL (prod) emits
    SELECT ... FOR UPDATE which serializes concurrent redemptions. We
    verify by source-inspection — the actual lock behavior needs a Postgres
    integration test, but the absence of with_for_update() is a regression
    we can catch here.
    """
    import inspect
    src = inspect.getsource(redeem_code)
    assert "with_for_update" in src, (
        "redeem_code must call with_for_update() on the ActivationCode "
        "SELECT to serialize concurrent redemptions on Postgres."
    )
