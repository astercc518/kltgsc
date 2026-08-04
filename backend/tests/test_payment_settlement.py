import hashlib
import hmac
import json
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app.models.customer import Customer
from app.models.customer_user import CustomerUser
from app.models.sales_wallet import (
    OWNER_CUSTOMER_SALES,
    SalesWallet,
    SalesWalletTransaction,
)
from app.models.subscription import INV_PAID, INV_PENDING, Invoice
from app.models.wallet import CustomerWallet, WalletTransaction
from app.api.v1.endpoints import webhooks
from app.core.config import settings
from app.services import payment_settlement
from app.services.sales_wallet_service import SALES_WALLET_TOPUP_PLAN
from app.services.wallet_service import WALLET_TOPUP_PLAN


@pytest.fixture
def customer(session) -> Customer:
    row = Customer(email="wallet@example.test", hashed_password="unused-in-test")
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@pytest.fixture
def customer_sales(session, customer) -> CustomerUser:
    row = CustomerUser(
        customer_id=customer.id,
        email="sales@example.test",
        hashed_password="unused-in-test",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _invoice(
    session,
    customer: Customer,
    *,
    plan: str,
    sales_owner_id: int | None = None,
) -> Invoice:
    row = Invoice(
        customer_id=customer.id,
        plan=plan,
        amount_usd=100.0,
        amount_crypto=100.25,
        currency="USDT",
        network="TRC20",
        payment_address="test-address",
        status=INV_PENDING,
        description="test wallet topup",
        expires_at=datetime.utcnow() + timedelta(minutes=30),
        sales_owner_type=(OWNER_CUSTOMER_SALES if sales_owner_id else None),
        sales_owner_id=sales_owner_id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _settle(session, invoice_id: int, tx_hash: str = "test-hash"):
    from app.services.payment_settlement import settle_wallet_invoice

    return settle_wallet_invoice(session, invoice_id=invoice_id, tx_hash=tx_hash)


def test_customer_wallet_commit_failure_rolls_back_every_state(
    session, customer, monkeypatch
) -> None:
    invoice = _invoice(session, customer, plan=WALLET_TOPUP_PLAN)
    real_commit = session.commit

    def fail_commit() -> None:
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="injected commit failure"):
        _settle(session, invoice.id)
    monkeypatch.setattr(session, "commit", real_commit)
    session.expire_all()

    persisted_invoice = session.get(Invoice, invoice.id)
    wallet = session.get(CustomerWallet, customer.id)
    transactions = session.exec(select(WalletTransaction)).all()
    assert persisted_invoice.status == INV_PENDING
    assert wallet is None
    assert transactions == []


def test_customer_wallet_retry_and_replay_credit_exactly_once(
    session, customer, monkeypatch
) -> None:
    invoice = _invoice(session, customer, plan=WALLET_TOPUP_PLAN)
    real_commit = session.commit
    monkeypatch.setattr(
        session,
        "commit",
        lambda: (_ for _ in ()).throw(RuntimeError("first attempt fails")),
    )
    with pytest.raises(RuntimeError):
        _settle(session, invoice.id)
    monkeypatch.setattr(session, "commit", real_commit)

    first = _settle(session, invoice.id, "chain-hash")
    replay = _settle(session, invoice.id, "chain-hash")
    session.expire_all()

    wallet = session.get(CustomerWallet, customer.id)
    transactions = session.exec(select(WalletTransaction)).all()
    assert first.id == replay.id
    assert wallet.balance_cents == 10_000
    assert len(transactions) == 1
    assert session.get(Invoice, invoice.id).status == INV_PAID


def test_sales_wallet_commit_failure_rolls_back_every_state(
    session, customer, customer_sales, monkeypatch
) -> None:
    invoice = _invoice(
        session,
        customer,
        plan=SALES_WALLET_TOPUP_PLAN,
        sales_owner_id=customer_sales.id,
    )
    real_commit = session.commit
    monkeypatch.setattr(
        session,
        "commit",
        lambda: (_ for _ in ()).throw(RuntimeError("sales commit failure")),
    )
    with pytest.raises(RuntimeError, match="sales commit failure"):
        _settle(session, invoice.id)
    monkeypatch.setattr(session, "commit", real_commit)
    session.expire_all()

    wallet = session.get(SalesWallet, (OWNER_CUSTOMER_SALES, customer_sales.id))
    transactions = session.exec(select(SalesWalletTransaction)).all()
    assert session.get(Invoice, invoice.id).status == INV_PENDING
    assert wallet is None
    assert transactions == []


def test_sales_wallet_retry_and_replay_credit_exactly_once(
    session, customer, customer_sales
) -> None:
    invoice = _invoice(
        session,
        customer,
        plan=SALES_WALLET_TOPUP_PLAN,
        sales_owner_id=customer_sales.id,
    )

    first = _settle(session, invoice.id)
    replay = _settle(session, invoice.id)
    session.expire_all()

    wallet = session.get(SalesWallet, (OWNER_CUSTOMER_SALES, customer_sales.id))
    transactions = session.exec(select(SalesWalletTransaction)).all()
    assert first.id == replay.id
    assert wallet.balance_cents == 10_000
    assert len(transactions) == 1
    assert session.get(Invoice, invoice.id).status == INV_PAID


def test_paid_invoice_without_receipt_is_an_invariant_error(session, customer) -> None:
    from app.services.payment_settlement import PaymentSettlementError

    invoice = _invoice(session, customer, plan=WALLET_TOPUP_PLAN)
    invoice.status = INV_PAID
    session.add(invoice)
    session.commit()

    with pytest.raises(PaymentSettlementError, match="missing wallet transaction"):
        _settle(session, invoice.id)


def test_wallet_webhook_failure_keeps_invoice_retryable(
    client, session, customer, monkeypatch
) -> None:
    invoice = _invoice(session, customer, plan=WALLET_TOPUP_PLAN)
    secret = "test-nowpayments-secret"
    monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", secret)

    def fail_credit(*_args, **_kwargs):
        raise RuntimeError("injected wallet mutation failure")

    monkeypatch.setattr(
        webhooks,
        "credit_wallet_from_invoice",
        fail_credit,
        raising=False,
    )
    monkeypatch.setattr(
        payment_settlement,
        "credit_wallet_from_invoice",
        fail_credit,
    )
    payload = {
        "payment_id": 12345,
        "payment_status": "finished",
        "order_id": f"tg1-invoice-{invoice.id}",
        "payin_hash": "chain-hash",
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()

    response = client.post(
        "/api/v1/webhooks/nowpayments",
        content=raw,
        headers={
            "content-type": "application/json",
            "x-nowpayments-sig": signature,
        },
    )
    session.expire_all()

    assert response.status_code == 503
    assert session.get(Invoice, invoice.id).status == INV_PENDING
    assert session.exec(select(WalletTransaction)).all() == []
