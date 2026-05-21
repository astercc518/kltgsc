"""
Sales wallet service (Epic C2).

Single source of truth for balance changes on SalesWallet (customer_sales
and platform_sales). Mirrors wallet_service for CustomerWallet but keyed
by (owner_type, owner_id).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlmodel import Session, select

from app.core.config import settings
from app.models.customer import Customer
from app.models.customer_user import CustomerUser
from app.models.sales_wallet import (
    OWNER_CUSTOMER_SALES, OWNER_PLATFORM_SALES, SALES_OWNER_TYPES,
    SalesWallet, SalesWalletTransaction,
)
from app.models.subscription import (
    Invoice, INV_PAID, INV_PENDING, NETWORK_TRC20, NETWORKS,
)
from app.services.billing_service import (
    _get_payment_address, _generate_unique_amount,
)
from app.models.wallet import calculate_bonus_pct


class SalesWalletError(Exception):
    """Validation / state errors surfaced to API as 400."""


class InsufficientSalesBalanceError(SalesWalletError):
    """Raised by charge_sales when balance < amount."""


SALES_WALLET_TOPUP_PLAN = "sales_wallet_topup"


# ── Wallet provisioning ─────────────────────────────────────────────────


def get_or_create_wallet(
    session: Session, owner_type: str, owner_id: int,
) -> SalesWallet:
    if owner_type not in SALES_OWNER_TYPES:
        raise SalesWalletError(f"Invalid owner_type: {owner_type}")
    wallet = session.exec(
        select(SalesWallet).where(
            SalesWallet.owner_type == owner_type,
            SalesWallet.owner_id == owner_id,
        )
    ).first()
    if wallet is None:
        wallet = SalesWallet(owner_type=owner_type, owner_id=owner_id)
        session.add(wallet)
        session.commit()
        session.refresh(wallet)
    return wallet


def get_balance_cents(session: Session, owner_type: str, owner_id: int) -> int:
    return get_or_create_wallet(session, owner_type, owner_id).balance_cents


# ── Topup (customer_sales only via Invoice; platform_sales via admin credit) ─


def create_topup_invoice_for_customer_sales(
    session: Session,
    customer_user: CustomerUser,
    amount_usd: float,
    network: str = NETWORK_TRC20,
) -> Tuple[Invoice, int, int]:
    """Create a pending USDT invoice that will credit the sub-user's
    sales wallet on payment. Parent customer is recorded on the invoice
    for accounting; the sales_owner_* columns route the credit."""
    if network not in NETWORKS:
        raise SalesWalletError(f"Unsupported network: {network}")
    if amount_usd < 20:
        raise SalesWalletError("Minimum sales topup is $20")
    if amount_usd > 5000:
        raise SalesWalletError("Maximum single sales topup is $5,000")

    address = _get_payment_address(network)

    # Idempotency on open pending invoice
    existing = session.exec(
        select(Invoice).where(
            Invoice.customer_id == customer_user.customer_id,
            Invoice.plan == SALES_WALLET_TOPUP_PLAN,
            Invoice.network == network,
            Invoice.amount_usd == amount_usd,
            Invoice.sales_owner_type == OWNER_CUSTOMER_SALES,
            Invoice.sales_owner_id == customer_user.id,
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
        customer_id=customer_user.customer_id,
        subscription_id=None,
        plan=SALES_WALLET_TOPUP_PLAN,
        amount_usd=amount_usd,
        amount_crypto=amount_crypto,
        currency="USDT",
        network=network,
        payment_address=address,
        status=INV_PENDING,
        description=(
            f"Sales wallet topup ${amount_usd:.0f} ({customer_user.email})"
            + (f" (+{bonus_pct}% bonus)" if bonus_pct else "")
        ),
        expires_at=now + timedelta(minutes=settings.INVOICE_EXPIRE_MINUTES),
        sales_owner_type=OWNER_CUSTOMER_SALES,
        sales_owner_id=customer_user.id,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice, bonus_pct, bonus_cents


def credit_sales_wallet_from_invoice(
    session: Session, invoice: Invoice,
) -> SalesWalletTransaction:
    """Apply a paid sales_wallet_topup invoice to the SalesWallet.

    Idempotent on invoice id. Caller is responsible for marking invoice
    status=paid before calling. See webhooks.py / billing_service.
    """
    if invoice.plan != SALES_WALLET_TOPUP_PLAN:
        raise SalesWalletError(
            f"Invoice {invoice.id} is not a sales topup (plan={invoice.plan})"
        )
    if invoice.status != INV_PAID:
        raise SalesWalletError(f"Invoice {invoice.id} not paid (status={invoice.status})")
    if not invoice.sales_owner_type or not invoice.sales_owner_id:
        raise SalesWalletError(f"Invoice {invoice.id} missing sales_owner_*")

    idem = f"sales-topup-invoice-{invoice.id}"
    existing = session.exec(
        select(SalesWalletTransaction).where(
            SalesWalletTransaction.idempotency_key == idem,
        )
    ).first()
    if existing:
        return existing

    bonus_pct = calculate_bonus_pct(invoice.amount_usd)
    base_cents = int(round(invoice.amount_usd * 100))
    bonus_cents = int(round(base_cents * bonus_pct / 100))
    credit_cents = base_cents + bonus_cents

    get_or_create_wallet(session, invoice.sales_owner_type, invoice.sales_owner_id)
    wallet = session.exec(
        select(SalesWallet)
        .where(
            SalesWallet.owner_type == invoice.sales_owner_type,
            SalesWallet.owner_id == invoice.sales_owner_id,
        )
        .with_for_update()
    ).one()

    wallet.balance_cents += credit_cents
    wallet.total_topup_cents += credit_cents
    wallet.updated_at = datetime.utcnow()

    desc = f"Topup ${invoice.amount_usd:.0f}"
    if bonus_pct:
        desc += f" (+${bonus_cents/100:.0f} bonus @ {bonus_pct}%)"

    txn = SalesWalletTransaction(
        owner_type=invoice.sales_owner_type,
        owner_id=invoice.sales_owner_id,
        type="topup",
        amount_cents=credit_cents,
        balance_after_cents=wallet.balance_cents,
        description=desc,
        invoice_id=invoice.id,
        idempotency_key=idem,
    )
    session.add(wallet)
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn


def admin_credit_platform_sales(
    session: Session,
    user_id: int,
    amount_cents: int,
    description: str,
    idempotency_key: str,
) -> SalesWalletTransaction:
    """Admin top-up path for platform_sales (User.role='sales') wallets.
    No invoice; admin grants budget directly. Idempotent on key.
    """
    if amount_cents <= 0:
        raise SalesWalletError("amount_cents must be positive")
    existing = session.exec(
        select(SalesWalletTransaction).where(
            SalesWalletTransaction.idempotency_key == idempotency_key,
        )
    ).first()
    if existing:
        return existing

    get_or_create_wallet(session, OWNER_PLATFORM_SALES, user_id)
    wallet = session.exec(
        select(SalesWallet).where(
            SalesWallet.owner_type == OWNER_PLATFORM_SALES,
            SalesWallet.owner_id == user_id,
        ).with_for_update()
    ).one()
    wallet.balance_cents += amount_cents
    wallet.total_topup_cents += amount_cents
    wallet.updated_at = datetime.utcnow()
    txn = SalesWalletTransaction(
        owner_type=OWNER_PLATFORM_SALES,
        owner_id=user_id,
        type="adjust",
        amount_cents=amount_cents,
        balance_after_cents=wallet.balance_cents,
        description=description[:200],
        idempotency_key=idempotency_key,
    )
    session.add(wallet)
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn


# ── Charge (used by Epic D lead-view) ──────────────────────────────────


def charge_sales(
    session: Session,
    owner_type: str,
    owner_id: int,
    amount_cents: int,
    idempotency_key: str,
    description: str = "",
    lead_id: Optional[int] = None,
) -> SalesWalletTransaction:
    """Atomically deduct from the sales wallet. Idempotent. Row-locked."""
    if amount_cents <= 0:
        raise SalesWalletError("amount_cents must be positive")
    if owner_type not in SALES_OWNER_TYPES:
        raise SalesWalletError(f"Invalid owner_type: {owner_type}")

    existing = session.exec(
        select(SalesWalletTransaction).where(
            SalesWalletTransaction.idempotency_key == idempotency_key,
        )
    ).first()
    if existing:
        return existing

    get_or_create_wallet(session, owner_type, owner_id)
    wallet = session.exec(
        select(SalesWallet).where(
            SalesWallet.owner_type == owner_type,
            SalesWallet.owner_id == owner_id,
        ).with_for_update()
    ).one()

    if wallet.balance_cents < amount_cents:
        raise InsufficientSalesBalanceError(
            f"Sales wallet balance {wallet.balance_cents}c < required {amount_cents}c"
        )

    wallet.balance_cents -= amount_cents
    wallet.total_spent_cents += amount_cents
    wallet.updated_at = datetime.utcnow()

    txn = SalesWalletTransaction(
        owner_type=owner_type,
        owner_id=owner_id,
        type="charge",
        amount_cents=-amount_cents,
        balance_after_cents=wallet.balance_cents,
        description=description[:200],
        lead_id=lead_id,
        idempotency_key=idempotency_key,
    )
    session.add(wallet)
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn


def list_transactions(
    session: Session,
    owner_type: str,
    owner_id: int,
    type_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[SalesWalletTransaction]:
    stmt = select(SalesWalletTransaction).where(
        SalesWalletTransaction.owner_type == owner_type,
        SalesWalletTransaction.owner_id == owner_id,
    )
    if type_filter:
        stmt = stmt.where(SalesWalletTransaction.type == type_filter)
    return list(session.exec(
        stmt.order_by(SalesWalletTransaction.created_at.desc())
            .offset(skip).limit(limit)
    ).all())
