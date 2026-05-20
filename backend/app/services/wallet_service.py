"""
Wallet service — single source of truth for wallet balance changes.

All balance mutations must go through this service to ensure:
- Atomic UPDATE via row lock (FOR UPDATE)
- Idempotency via wallet_transaction.idempotency_key UNIQUE
- Audit trail (one wallet_transaction row per change with balance_after snapshot)

Topup flow:
    1. create_topup_invoice(customer, amount_usd, network)
         → Invoice(plan='wallet_topup', status=pending) committed
         → frontend shows USDT addr + amount_crypto for transfer
    2. credit_wallet_from_invoice(invoice)
         → called by webhook/admin once payment confirmed
         → balance += amount + bonus, idempotent

Charge flow (Bulk Send W3):
    charge_wallet(customer_id, amount_cents, bulk_batch_id, idempotency_key)
         → row-lock wallet, deduct, write txn, raise InsufficientBalance if needed

参考 docs/planning/bulk_send_spec.md §3.2
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models.customer import Customer
from app.models.subscription import (
    Invoice, INV_PAID, INV_PENDING,
    NETWORK_TRC20, NETWORKS,
)
from app.models.wallet import (
    CustomerWallet, WalletTransaction,
    TXN_TOPUP, TXN_CHARGE, TXN_REFUND, TXN_ADJUST,
    calculate_bonus_pct,
)
from app.services.billing_service import (
    BillingError, _get_payment_address, _generate_unique_amount,
)


# plan code used for wallet-topup invoices (distinct from subscription plans)
WALLET_TOPUP_PLAN = "wallet_topup"


class WalletError(Exception):
    """Validation / state errors surfaced to API as 400."""


class InsufficientBalanceError(WalletError):
    """Raised by charge_wallet when balance < amount."""


# ── Wallet provisioning ─────────────────────────────────────────────────


def get_or_create_wallet(session: Session, customer_id: int) -> CustomerWallet:
    """Return the customer's wallet, creating an empty one on first access."""
    wallet = session.get(CustomerWallet, customer_id)
    if wallet is None:
        wallet = CustomerWallet(customer_id=customer_id)
        session.add(wallet)
        session.commit()
        session.refresh(wallet)
    return wallet


# ── Topup: create invoice ───────────────────────────────────────────────


def create_topup_invoice(
    session: Session,
    customer: Customer,
    amount_usd: float,
    network: str = NETWORK_TRC20,
) -> tuple[Invoice, int, int]:
    """Create a pending USDT invoice for wallet topup.

    Returns (invoice, bonus_pct, bonus_cents). The caller should show the
    invoice to the customer with the bonus information.

    The actual wallet credit happens later in credit_wallet_from_invoice()
    after payment confirmation (via webhook or admin manual confirmation).
    """
    if network not in NETWORKS:
        raise WalletError(f"Unsupported network: {network}")
    if amount_usd < 100:
        raise WalletError("Minimum topup is $100")
    if amount_usd > 50000:
        raise WalletError("Maximum single topup is $50,000")

    address = _get_payment_address(network)

    # Idempotency: reuse open pending topup if same amount + network
    existing = session.exec(
        select(Invoice).where(
            Invoice.customer_id == customer.id,
            Invoice.plan == WALLET_TOPUP_PLAN,
            Invoice.network == network,
            Invoice.amount_usd == amount_usd,
            Invoice.status == INV_PENDING,
            Invoice.expires_at > datetime.utcnow(),
        )
    ).first()

    bonus_pct = calculate_bonus_pct(amount_usd)
    bonus_cents = int(round(amount_usd * 100 * bonus_pct / 100))

    if existing:
        return existing, bonus_pct, bonus_cents

    amount_crypto = _generate_unique_amount(session, amount_usd, network)

    now = datetime.utcnow()
    invoice = Invoice(
        customer_id=customer.id,
        subscription_id=None,  # wallet topup is not tied to a subscription
        plan=WALLET_TOPUP_PLAN,
        amount_usd=amount_usd,
        amount_crypto=amount_crypto,
        currency="USDT",
        network=network,
        payment_address=address,
        status=INV_PENDING,
        description=(
            f"Wallet topup ${amount_usd:.0f}"
            + (f" (+{bonus_pct}% bonus)" if bonus_pct else "")
        ),
        expires_at=now + timedelta(minutes=settings.INVOICE_EXPIRE_MINUTES),
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice, bonus_pct, bonus_cents


# ── Topup: credit wallet after payment confirmation ─────────────────────


def credit_wallet_from_invoice(
    session: Session,
    invoice: Invoice,
) -> WalletTransaction:
    """Apply a confirmed topup invoice to the customer's wallet balance.

    Idempotent: keyed by invoice.id. Calling twice with the same paid invoice
    returns the existing WalletTransaction without double-crediting.

    Caller is responsible for marking invoice.status=paid (typically via
    billing_service.activate_invoice or webhook handler) before calling.
    """
    if invoice.plan != WALLET_TOPUP_PLAN:
        raise WalletError(
            f"Invoice {invoice.id} is not a wallet topup (plan={invoice.plan})"
        )
    if invoice.status != INV_PAID:
        raise WalletError(
            f"Invoice {invoice.id} is not paid (status={invoice.status})"
        )

    idempotency_key = f"topup-invoice-{invoice.id}"

    # Idempotency check first
    existing = session.exec(
        select(WalletTransaction).where(
            WalletTransaction.idempotency_key == idempotency_key
        )
    ).first()
    if existing:
        return existing

    # Calculate credit: amount + bonus
    bonus_pct = calculate_bonus_pct(invoice.amount_usd)
    base_cents = int(round(invoice.amount_usd * 100))
    bonus_cents = int(round(base_cents * bonus_pct / 100))
    credit_cents = base_cents + bonus_cents

    # Lock the wallet row, mutate, write txn — all in one transaction
    wallet = get_or_create_wallet(session, invoice.customer_id)

    # Re-fetch with row lock to handle concurrent topups
    wallet = session.exec(
        select(CustomerWallet)
        .where(CustomerWallet.customer_id == invoice.customer_id)
        .with_for_update()
    ).one()

    wallet.balance_cents += credit_cents
    wallet.total_topup_cents += credit_cents
    wallet.updated_at = datetime.utcnow()

    description = f"Topup ${invoice.amount_usd:.0f}"
    if bonus_pct:
        description += f" (+${bonus_cents/100:.0f} bonus @ {bonus_pct}%)"

    txn = WalletTransaction(
        customer_id=invoice.customer_id,
        type=TXN_TOPUP,
        amount_cents=credit_cents,
        balance_after_cents=wallet.balance_cents,
        description=description,
        invoice_id=invoice.id,
        idempotency_key=idempotency_key,
    )
    session.add(wallet)
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn


# ── Charge wallet (used by Bulk Send W3) ────────────────────────────────


def charge_wallet(
    session: Session,
    customer_id: int,
    amount_cents: int,
    idempotency_key: str,
    description: str = "",
    bulk_batch_id: Optional[int] = None,
) -> WalletTransaction:
    """Atomically deduct from wallet balance.

    Uses SELECT ... FOR UPDATE to serialize concurrent charges to the same
    customer. Idempotent via idempotency_key — same key returns the previous
    txn instead of charging twice.

    Raises:
        InsufficientBalanceError if balance < amount_cents
    """
    if amount_cents <= 0:
        raise WalletError("amount_cents must be positive")

    # Idempotency check first (cheap)
    existing = session.exec(
        select(WalletTransaction).where(
            WalletTransaction.idempotency_key == idempotency_key
        )
    ).first()
    if existing:
        return existing

    get_or_create_wallet(session, customer_id)

    # Lock the wallet row
    wallet = session.exec(
        select(CustomerWallet)
        .where(CustomerWallet.customer_id == customer_id)
        .with_for_update()
    ).one()

    if wallet.balance_cents < amount_cents:
        raise InsufficientBalanceError(
            f"Wallet balance {wallet.balance_cents}c < required {amount_cents}c"
        )

    wallet.balance_cents -= amount_cents
    wallet.total_spent_cents += amount_cents
    wallet.updated_at = datetime.utcnow()

    txn = WalletTransaction(
        customer_id=customer_id,
        type=TXN_CHARGE,
        amount_cents=-amount_cents,
        balance_after_cents=wallet.balance_cents,
        description=description,
        bulk_batch_id=bulk_batch_id,
        idempotency_key=idempotency_key,
    )
    session.add(wallet)
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn


# ── Read helpers ────────────────────────────────────────────────────────


def get_balance_cents(session: Session, customer_id: int) -> int:
    """Cheap balance lookup. Auto-provisions empty wallet on first access."""
    wallet = get_or_create_wallet(session, customer_id)
    return wallet.balance_cents


def list_transactions(
    session: Session,
    customer_id: int,
    type_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[WalletTransaction]:
    """Paginated transaction history (most recent first)."""
    stmt = select(WalletTransaction).where(
        WalletTransaction.customer_id == customer_id
    )
    if type_filter:
        stmt = stmt.where(WalletTransaction.type == type_filter)
    rows = session.exec(
        stmt.order_by(WalletTransaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return list(rows)
