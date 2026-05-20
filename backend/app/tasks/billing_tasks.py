"""
Epic 2.5 — Billing automation tasks (Celery beat).

Removes the manual ops involvement for the lifecycle bits that don't need
ops judgement, while keeping admin in the loop for actual payment confirmation:

  • expire_pending_invoices  — every 5 min
        Marks Invoice rows whose expires_at has passed as 'expired' so they
        stop showing up in customer dashboards / admin pending lists.

  • sweep_expired_subscriptions — hourly
        When a Subscription.period_end has passed without renewal, mark the
        subscription 'expired' and suspend the customer (status='suspended')
        so quota-consuming endpoints start returning 402.

  • send_renewal_reminders — daily
        Find subscriptions ending in the next 7 days and broadcast a
        'renewal_reminder' WebSocket event to that customer's portal session.
        (Email is intentionally out of MVP scope — no SMTP configured.)

All three are idempotent: re-running them produces no extra state changes
once their condition has been satisfied.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.models.customer import Customer, STATUS_ACTIVE, STATUS_SUSPENDED
from app.models.subscription import (
    INV_EXPIRED,
    INV_PENDING,
    Invoice,
    SUB_ACTIVE,
    SUB_EXPIRED,
    Subscription,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 1) Invoice expiry sweep
# ──────────────────────────────────────────────────────────────────────────

@shared_task(name="app.tasks.billing_tasks.expire_pending_invoices")
def expire_pending_invoices() -> dict:
    """Mark pending invoices past expires_at as 'expired'.

    Returns a dict with the count of invoices touched (useful for logs/Flower).
    """
    now = datetime.utcnow()
    with Session(engine) as session:
        stale = session.exec(
            select(Invoice).where(
                Invoice.status == INV_PENDING,
                Invoice.expires_at < now,
            )
        ).all()
        for inv in stale:
            inv.status = INV_EXPIRED
            session.add(inv)
        if stale:
            session.commit()
    if stale:
        logger.info("expire_pending_invoices: marked %d invoices expired", len(stale))
    return {"expired": len(stale)}


# ──────────────────────────────────────────────────────────────────────────
# 2) Subscription expiry sweep + customer suspension
# ──────────────────────────────────────────────────────────────────────────

@shared_task(name="app.tasks.billing_tasks.sweep_expired_subscriptions")
def sweep_expired_subscriptions() -> dict:
    """Expire active subscriptions past period_end and suspend their customers.

    A customer can still log in to the portal in suspended state and see
    their billing page — they just can't consume quota (get_active_customer
    returns 402). Re-subscribing restores access.
    """
    now = datetime.utcnow()
    suspended_count = 0
    with Session(engine) as session:
        stale = session.exec(
            select(Subscription).where(
                Subscription.status == SUB_ACTIVE,
                Subscription.period_end < now,
            )
        ).all()
        for sub in stale:
            sub.status = SUB_EXPIRED
            session.add(sub)

            # Suspend customer (only if no newer active sub took over)
            customer = session.get(Customer, sub.customer_id)
            if customer and customer.status == STATUS_ACTIVE:
                # Defensive: check there isn't another active sub (race-safe)
                still_active = session.exec(
                    select(Subscription).where(
                        Subscription.customer_id == customer.id,
                        Subscription.status == SUB_ACTIVE,
                        Subscription.id != sub.id,
                    )
                ).first()
                if not still_active:
                    customer.status = STATUS_SUSPENDED
                    customer.subscription_status = SUB_EXPIRED
                    customer.updated_at = now
                    session.add(customer)
                    suspended_count += 1
        if stale:
            session.commit()
    if stale:
        logger.info(
            "sweep_expired_subscriptions: expired %d subs, suspended %d customers",
            len(stale), suspended_count,
        )
    return {"expired_subs": len(stale), "suspended_customers": suspended_count}


# ──────────────────────────────────────────────────────────────────────────
# 3) Renewal reminders
# ──────────────────────────────────────────────────────────────────────────

@shared_task(name="app.tasks.billing_tasks.send_renewal_reminders")
def send_renewal_reminders(warn_days: int = 7) -> dict:
    """Broadcast a renewal-reminder event for subs ending within `warn_days`.

    Uses the existing ws_manager (admin notification channel) so the customer's
    portal session — if open — sees a toast. No email yet (MVP).
    """
    # Lazy import to avoid pulling websocket deps into beat worker if it's
    # ever split off; also breaks any latent circular import.
    try:
        from app.services.websocket_manager import ws_manager
    except Exception as e:  # noqa: BLE001
        logger.warning("renewal_reminders: ws_manager not available (%s)", e)
        ws_manager = None  # type: ignore

    now = datetime.utcnow()
    cutoff = now + timedelta(days=warn_days)
    reminded = 0
    with Session(engine) as session:
        candidates = session.exec(
            select(Subscription).where(
                Subscription.status == SUB_ACTIVE,
                Subscription.period_end > now,
                Subscription.period_end <= cutoff,
            )
        ).all()
        for sub in candidates:
            customer = session.get(Customer, sub.customer_id)
            if not customer:
                continue
            days_left = max(0, (sub.period_end - now).days)
            payload = {
                "type": "renewal_reminder",
                "customer_id": customer.id,
                "subscription_id": sub.id,
                "plan": sub.plan,
                "days_left": days_left,
                "period_end": sub.period_end.isoformat(),
            }
            if ws_manager:
                try:
                    # broadcast is async; the beat task is sync — run in a
                    # fresh loop. If ws_manager has no listeners this is a no-op.
                    import asyncio
                    asyncio.run(ws_manager.broadcast(payload))
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "renewal_reminders: ws broadcast failed for customer %s: %s",
                        customer.id, e,
                    )
            reminded += 1
    if reminded:
        logger.info("send_renewal_reminders: notified %d customers", reminded)
    return {"reminded": reminded}
