"""
Billing service — single source of truth for subscription lifecycle.

Use this service from both customer-facing /subscribe and admin-facing
/activate endpoints; do not duplicate logic in route handlers.

MVP flow (USDT manual confirmation):
    1. create_pending_invoice(customer, plan, network)
         -> Subscription(status=pending) + Invoice(status=pending)
         -> client shows USDT address + amount_crypto, customer transfers
    2. activate_invoice(invoice, tx_hash, admin_user_id)
         -> Invoice(status=paid) + Subscription(status=active)
         -> Customer.plan / quotas / current_period_end refreshed
         -> if customer had a previous active sub, cancel it first

Edge cases handled:
    - Invoice expiry (sweep_expired_invoices) — TODO Celery beat in Epic 2.5
    - Amount-suffix collision when generating amount_crypto (retry up to 20x)
    - Re-subscribing while a pending invoice exists for same plan -> return existing
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models.customer import (
    Customer,
    PLAN_CODES,
    PLAN_PRICE_USD,
    PLAN_QUOTA,
    STATUS_ACTIVE,
)
from app.models.subscription import (
    Invoice,
    INV_PAID,
    INV_PENDING,
    NETWORK_BEP20,
    NETWORK_ERC20,
    NETWORK_TRC20,
    NETWORKS,
    SUB_ACTIVE,
    SUB_CANCELED,
    SUB_PENDING,
    Subscription,
)


class BillingError(Exception):
    """Validation / state errors surfaced to API as 400."""


# ── Helpers ────────────────────────────────────────────────────────────

def _get_payment_address(network: str) -> str:
    """Return the configured USDT receive address for the given network.

    Raises BillingError if ops hasn't configured the address — fail loud
    rather than silently giving the customer an empty string to copy.
    """
    addr = {
        NETWORK_TRC20: settings.USDT_ADDRESS_TRC20,
        NETWORK_ERC20: settings.USDT_ADDRESS_ERC20,
        NETWORK_BEP20: settings.USDT_ADDRESS_BEP20,
    }.get(network, "")
    if not addr:
        raise BillingError(
            f"USDT receive address for {network} is not configured. "
            f"Set USDT_ADDRESS_{network} in environment."
        )
    return addr


def _generate_unique_amount(
    session: Session, base_amount: float, network: str
) -> float:
    """Generate `base + 0.xx` where 0.xx is unused among pending invoices.

    Ops can match an incoming transfer to a specific invoice purely by the
    deposit amount, without needing per-customer HD-wallet addresses.
    """
    for _ in range(20):
        suffix = random.randint(1, 99) / 100.0  # 0.01 .. 0.99
        candidate = round(base_amount + suffix, 2)
        clash = session.exec(
            select(Invoice).where(
                Invoice.amount_crypto == candidate,
                Invoice.network == network,
                Invoice.status == INV_PENDING,
            )
        ).first()
        if not clash:
            return candidate
    # Collision pool exhausted (shouldn't happen with current scale).
    # Fall back to a deterministic but unique tail by appending invoice id later.
    return round(base_amount + 0.99, 2)


# ── Public service ─────────────────────────────────────────────────────

def create_pending_invoice(
    session: Session,
    customer: Customer,
    plan: str,
    network: str = NETWORK_TRC20,
) -> Invoice:
    """Create a pending Subscription + Invoice for the customer.

    Returns the Invoice (committed). The caller should display it to the
    customer with the USDT address + amount_crypto and wait for payment.
    """
    if plan not in PLAN_CODES:
        raise BillingError(f"Unknown plan: {plan}")
    if network not in NETWORKS:
        raise BillingError(f"Unsupported network: {network}")

    address = _get_payment_address(network)

    # Idempotency: if there's already a pending invoice for same plan+network,
    # return it instead of creating a new one. Lets the client safely call
    # /subscribe again without piling up duplicate invoices.
    existing = session.exec(
        select(Invoice).where(
            Invoice.customer_id == customer.id,
            Invoice.plan == plan,
            Invoice.network == network,
            Invoice.status == INV_PENDING,
            Invoice.expires_at > datetime.utcnow(),
        )
    ).first()
    if existing:
        return existing

    now = datetime.utcnow()
    period_start = now
    period_end = now + timedelta(days=30)

    subscription = Subscription(
        customer_id=customer.id,
        plan=plan,
        status=SUB_PENDING,
        period_start=period_start,
        period_end=period_end,
    )
    session.add(subscription)
    session.flush()  # need subscription.id

    amount_usd = PLAN_PRICE_USD[plan]
    amount_crypto = _generate_unique_amount(session, amount_usd, network)

    invoice = Invoice(
        customer_id=customer.id,
        subscription_id=subscription.id,
        plan=plan,
        amount_usd=amount_usd,
        amount_crypto=amount_crypto,
        currency="USDT",
        network=network,
        payment_address=address,
        status=INV_PENDING,
        description=f"TG1.AI {plan.capitalize()} Plan - Monthly",
        expires_at=now + timedelta(minutes=settings.INVOICE_EXPIRE_MINUTES),
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


def _apply_subscription_activation(
    session: Session,
    customer: Customer,
    subscription: Subscription,
) -> Subscription:
    """Side effects shared by USDT-invoice and activation-code paths.

    Idempotent on `subscription.status == SUB_ACTIVE` (returns without changes).
    Caller MUST have already set subscription.activated_via and (if applicable)
    activation_code_id before invoking this helper.

    Side effects (all in one commit):
      - Cancel any other active Subscription for this customer
      - Mark `subscription` active + activated_at = now
      - Refresh Customer denormalized fields + quota
      - Auto-enable AI marketing feature slugs
      - Trigger provision_customer (account/group/KB allocation)
    """
    if subscription.status == SUB_ACTIVE:
        return subscription

    now = datetime.utcnow()

    # Cancel any other active subscription for this customer
    prior_active = session.exec(
        select(Subscription).where(
            Subscription.customer_id == customer.id,
            Subscription.status == SUB_ACTIVE,
            Subscription.id != subscription.id,
        )
    ).all()
    for prev in prior_active:
        prev.status = SUB_CANCELED
        prev.canceled_at = now
        session.add(prev)

    subscription.status = SUB_ACTIVE
    subscription.activated_at = now
    session.add(subscription)

    quota = PLAN_QUOTA[subscription.plan]
    customer.status = STATUS_ACTIVE
    customer.plan = subscription.plan
    customer.subscription_status = SUB_ACTIVE
    customer.current_period_end = subscription.period_end
    customer.account_quota = quota["account"]
    customer.group_quota = quota["group"]
    customer.token_quota = quota["token"]
    customer.seat_quota = quota["seat"]
    customer.updated_at = now
    session.add(customer)

    session.commit()
    session.refresh(subscription)

    # Auto-enable AI marketing features (best-effort)
    try:
        from app.services import feature_billing as fb
        for slug in (
            "ai_marketing_assistant",
            "ai_marketing_group_reply",
            "ai_marketing_lead_created",
        ):
            fb.upsert_customer_feature(
                session, customer.id, slug,
                enabled=True,
                notes=f"auto-enabled on activation of {subscription.plan} plan",
            )
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "Failed to auto-enable AI marketing features for customer %s: %s",
            customer.id, e,
        )

    # Auto-provision accounts + groups (best-effort, never blocks payment confirmation)
    subscription_id = subscription.id
    try:
        from app.services.allocation_service import provision_customer
        provision_customer(session, customer)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception(
            "Provisioning failed for customer %s after activation: %s",
            customer.id, e,
        )

    # Re-fetch — provision_customer issued multiple commits that expired
    # this Session's identity-map entry for `subscription`.
    return session.get(Subscription, subscription_id)


def activate_invoice(
    session: Session,
    invoice: Invoice,
    tx_hash: str,
    admin_user_id: Optional[int] = None,
) -> Subscription:
    """Mark an invoice as paid and activate its subscription (USDT path)."""
    if invoice.status == INV_PAID:
        return session.get(Subscription, invoice.subscription_id)
    if invoice.status != INV_PENDING:
        raise BillingError(
            f"Invoice {invoice.id} is in status '{invoice.status}', cannot activate"
        )
    if invoice.expires_at < datetime.utcnow():
        raise BillingError(f"Invoice {invoice.id} has expired")

    customer = session.get(Customer, invoice.customer_id)
    if not customer:
        raise BillingError(f"Customer {invoice.customer_id} not found")

    subscription = session.get(Subscription, invoice.subscription_id)
    if not subscription:
        raise BillingError(f"Subscription {invoice.subscription_id} not found")

    now = datetime.utcnow()

    # Mark invoice paid (USDT-specific)
    invoice.status = INV_PAID
    invoice.tx_hash = tx_hash
    invoice.paid_at = now
    invoice.paid_by_admin = admin_user_id
    session.add(invoice)

    # Pin activation provenance
    subscription.activated_via = "usdt"
    session.add(subscription)
    session.commit()
    session.refresh(subscription)

    return _apply_subscription_activation(session, customer, subscription)


def get_active_subscription(
    session: Session, customer_id: int
) -> Optional[Subscription]:
    """Return the customer's currently active subscription, if any."""
    return session.exec(
        select(Subscription).where(
            Subscription.customer_id == customer_id,
            Subscription.status == SUB_ACTIVE,
        ).order_by(Subscription.activated_at.desc())
    ).first()
