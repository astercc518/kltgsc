"""Lock in activate_invoice behavior before extracting _apply_subscription_activation.

These tests must pass against the CURRENT activate_invoice (pre-refactor)
and continue to pass after the refactor in Task 8. Any drift = regression.
"""
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models.customer import Customer, STATUS_ACTIVE
from app.models.subscription import (
    Invoice,
    INV_PENDING,
    INV_PAID,
    SUB_ACTIVE,
    SUB_PENDING,
    SUB_CANCELED,
    Subscription,
)
from app.services.billing_service import activate_invoice


@pytest.fixture
def customer(session):
    c = Customer(
        email="t@t.t",
        hashed_password="x",
        status="pending",
        plan=None,
        account_quota=0, group_quota=0, token_quota=0, seat_quota=0,
    )
    session.add(c); session.commit(); session.refresh(c)
    return c


def _make_pending(session, customer, plan="starter"):
    now = datetime.utcnow()
    sub = Subscription(
        customer_id=customer.id, plan=plan, status=SUB_PENDING,
        period_start=now, period_end=now + timedelta(days=30),
    )
    session.add(sub); session.flush()
    inv = Invoice(
        customer_id=customer.id, subscription_id=sub.id,
        plan=plan, amount_usd=199.0, amount_crypto=199.5, currency="USDT",
        network="TRC20", payment_address="addr",
        status=INV_PENDING, description="test",
        expires_at=now + timedelta(minutes=30),
    )
    session.add(inv); session.commit(); session.refresh(inv)
    return inv, sub


def test_activate_invoice_marks_invoice_paid(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    result_sub = activate_invoice(session, inv, tx_hash="0xabc", admin_user_id=1)
    session.refresh(inv)
    assert inv.status == INV_PAID
    assert inv.tx_hash == "0xabc"
    assert inv.paid_at is not None
    assert inv.paid_by_admin == 1


def test_activate_invoice_activates_subscription(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    result_sub = activate_invoice(session, inv, tx_hash="0xabc")
    assert result_sub.status == SUB_ACTIVE
    assert result_sub.activated_at is not None


def test_activate_invoice_cancels_prior_active(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    # Pre-existing active subscription on a different plan
    now = datetime.utcnow()
    prior = Subscription(
        customer_id=customer.id, plan="starter", status=SUB_ACTIVE,
        period_start=now - timedelta(days=10), period_end=now + timedelta(days=20),
        activated_at=now - timedelta(days=10),
    )
    session.add(prior); session.commit(); session.refresh(prior)

    inv, new_sub = _make_pending(session, customer, plan="growth")
    activate_invoice(session, inv, tx_hash="0xdef")

    session.refresh(prior)
    assert prior.status == SUB_CANCELED
    assert prior.canceled_at is not None


def test_activate_invoice_refreshes_customer_denormalized(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer, plan="growth")
    activate_invoice(session, inv, tx_hash="0xghi")
    session.refresh(customer)
    assert customer.status == STATUS_ACTIVE
    assert customer.plan == "growth"
    assert customer.subscription_status == SUB_ACTIVE
    # quota fields should be set to plan defaults
    assert customer.account_quota > 0
    assert customer.group_quota > 0


def test_activate_invoice_is_idempotent_on_paid_invoice(session, customer, monkeypatch):
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    activate_invoice(session, inv, tx_hash="0xabc")
    # Second call must not raise / must not double-activate
    result = activate_invoice(session, inv, tx_hash="0xabc")
    assert result.id == sub.id
    assert result.status == SUB_ACTIVE


def test_activate_invoice_sets_activated_via_usdt(session, customer, monkeypatch):
    """Pin Epic 1: USDT path OVERWRITES activated_via to 'usdt' (not just default).

    Pre-set the field to a non-default value so the test fails if
    activate_invoice ever stops writing it explicitly. This is the regression
    safety net for the line `subscription.activated_via = "usdt"` in
    billing_service.activate_invoice.
    """
    monkeypatch.setattr(
        "app.services.allocation_service.provision_customer",
        lambda s, c: None, raising=False,
    )
    inv, sub = _make_pending(session, customer)
    # Pre-set to a non-default value so the assertion proves activate_invoice
    # actually writes the field (rather than picking up the model default).
    sub.activated_via = "bogus_pretend_previous_state"
    session.add(sub)
    session.commit()

    result = activate_invoice(session, inv, tx_hash="0xabc")
    assert result.activated_via == "usdt"
    assert result.activation_code_id is None
