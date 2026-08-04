import os
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, create_engine, delete, select

from app.models.customer import Customer
from app.models.subscription import INV_EXPIRED, INV_PENDING, Invoice
from app.models.wallet import CustomerWallet, WalletTransaction
from app.services.payment_settlement import (
    PaymentSettlementError,
    settle_wallet_invoice,
)
from app.services.wallet_service import WALLET_TOPUP_PLAN


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL concurrency coverage",
)


def test_postgres_lock_refreshes_invoice_after_concurrent_terminal_update() -> None:
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    customer_id: int | None = None
    invoice_id: int | None = None

    try:
        with Session(engine) as setup:
            customer = Customer(
                email=f"settlement-{uuid4().hex}@example.test",
                hashed_password="unused-in-test",
            )
            setup.add(customer)
            setup.commit()
            setup.refresh(customer)
            customer_id = customer.id

            invoice = Invoice(
                customer_id=customer.id,
                plan=WALLET_TOPUP_PLAN,
                amount_usd=100.0,
                amount_crypto=100.25,
                currency="USDT",
                network="TRC20",
                payment_address="test-address",
                status=INV_PENDING,
                description="postgres settlement test",
                expires_at=datetime.utcnow() + timedelta(minutes=30),
            )
            setup.add(invoice)
            setup.commit()
            setup.refresh(invoice)
            invoice_id = invoice.id

        with Session(engine) as stale_session:
            cached = stale_session.get(Invoice, invoice_id)
            assert cached.status == INV_PENDING

            with Session(engine) as concurrent_session:
                current = concurrent_session.get(Invoice, invoice_id)
                current.status = INV_EXPIRED
                concurrent_session.add(current)
                concurrent_session.commit()

            with pytest.raises(PaymentSettlementError, match="status expired"):
                settle_wallet_invoice(
                    stale_session,
                    invoice_id=invoice_id,
                    tx_hash="must-not-settle",
                )

        with Session(engine) as verify:
            assert verify.get(Invoice, invoice_id).status == INV_EXPIRED
            assert verify.get(CustomerWallet, customer_id) is None
            assert verify.exec(
                select(WalletTransaction).where(
                    WalletTransaction.invoice_id == invoice_id
                )
            ).all() == []
    finally:
        if customer_id is not None:
            with Session(engine) as cleanup:
                if invoice_id is not None:
                    cleanup.exec(
                        delete(WalletTransaction).where(
                            WalletTransaction.invoice_id == invoice_id
                        )
                    )
                    cleanup.exec(delete(Invoice).where(Invoice.id == invoice_id))
                cleanup.exec(
                    delete(CustomerWallet).where(
                        CustomerWallet.customer_id == customer_id
                    )
                )
                cleanup.exec(delete(Customer).where(Customer.id == customer_id))
                cleanup.commit()
        engine.dispose()
