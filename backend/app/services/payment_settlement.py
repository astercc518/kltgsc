"""Atomic settlement for customer and customer-sales wallet invoices."""
from datetime import datetime
from typing import Union

from sqlmodel import Session, select

from app.models.sales_wallet import SalesWalletTransaction
from app.models.subscription import INV_PAID, INV_PENDING, Invoice
from app.models.wallet import WalletTransaction
from app.services.sales_wallet_service import (
    SALES_WALLET_TOPUP_PLAN,
    SalesWalletError,
    credit_sales_wallet_from_invoice,
)
from app.services.wallet_service import (
    WALLET_TOPUP_PLAN,
    WalletError,
    credit_wallet_from_invoice,
)


WalletReceipt = Union[WalletTransaction, SalesWalletTransaction]


class PaymentSettlementError(Exception):
    """Invoice state or wallet-credit invariant prevents settlement."""


def _existing_receipt(
    session: Session,
    invoice: Invoice,
) -> WalletReceipt | None:
    if invoice.plan == SALES_WALLET_TOPUP_PLAN:
        return session.exec(
            select(SalesWalletTransaction).where(
                SalesWalletTransaction.idempotency_key
                == f"sales-topup-invoice-{invoice.id}"
            )
        ).first()
    return session.exec(
        select(WalletTransaction).where(
            WalletTransaction.idempotency_key == f"topup-invoice-{invoice.id}"
        )
    ).first()


def settle_wallet_invoice(
    session: Session,
    *,
    invoice_id: int,
    tx_hash: str,
) -> WalletReceipt:
    """Mark one wallet invoice paid and create its credit in one transaction."""
    try:
        invoice = session.exec(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if not invoice:
            raise PaymentSettlementError(f"Invoice {invoice_id} not found")
        if invoice.plan not in {WALLET_TOPUP_PLAN, SALES_WALLET_TOPUP_PLAN}:
            raise PaymentSettlementError(
                f"Invoice {invoice.id} is not a wallet topup"
            )

        existing = _existing_receipt(session, invoice)
        if invoice.status == INV_PAID:
            if existing:
                return existing
            raise PaymentSettlementError(
                f"Paid invoice {invoice.id} missing wallet transaction"
            )
        if invoice.status != INV_PENDING:
            raise PaymentSettlementError(
                f"Invoice {invoice.id} cannot settle from status {invoice.status}"
            )
        if existing:
            raise PaymentSettlementError(
                f"Pending invoice {invoice.id} already has a wallet transaction"
            )

        invoice.status = INV_PAID
        invoice.tx_hash = tx_hash
        invoice.paid_at = datetime.utcnow()
        session.add(invoice)

        if invoice.plan == SALES_WALLET_TOPUP_PLAN:
            receipt = credit_sales_wallet_from_invoice(
                session,
                invoice,
                commit=False,
            )
        else:
            receipt = credit_wallet_from_invoice(
                session,
                invoice,
                commit=False,
            )

        session.commit()
        session.refresh(receipt)
        return receipt
    except (WalletError, SalesWalletError) as exc:
        session.rollback()
        raise PaymentSettlementError(str(exc)) from exc
    except Exception:
        session.rollback()
        raise
