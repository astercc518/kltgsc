"""
Bulk Send W5 — low-balance watcher.

Beat-scheduled task that scans every customer wallet and fires a one-shot
notification when the balance drops below LOW_BALANCE_THRESHOLD_CENTS. The
flag is cleared automatically on the next successful topup
(see wallet_service.credit_wallet_from_invoice).

Notification path:
  1. WebSocket broadcast (`low_balance_alert`) so any open portal sees it
  2. Saved-Messages to customer.main_account if bound (best-effort)

参考 docs/planning/bulk_send_spec.md §2.3
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.customer import Customer
from app.models.wallet import CustomerWallet


logger = logging.getLogger(__name__)


LOW_BALANCE_THRESHOLD_CENTS = 2000  # $20


@celery_app.task(
    bind=True,
    name="app.tasks.bulk_balance_watcher.scan_low_balance",
    soft_time_limit=120, time_limit=180,
)
def scan_low_balance(self) -> dict:
    """Scan all wallets; notify those that just dipped below the threshold.

    A wallet that has already been notified (low_balance_notified_at IS NOT NULL)
    is skipped — the flag clears on next topup, allowing the next dip to fire.
    """
    notified = 0
    skipped = 0
    examined = 0

    with Session(engine) as s:
        wallets = s.exec(
            select(CustomerWallet).where(
                CustomerWallet.balance_cents < LOW_BALANCE_THRESHOLD_CENTS,
            )
        ).all()

        for w in wallets:
            examined += 1
            if w.low_balance_notified_at is not None:
                skipped += 1
                continue

            customer = s.get(Customer, w.customer_id)
            if not customer:
                continue

            _broadcast_alert(customer, w)
            _send_via_main_account_best_effort(customer, w)

            w.low_balance_notified_at = datetime.utcnow()
            s.add(w)
            s.commit()
            notified += 1

    return {
        "examined": examined,
        "notified": notified,
        "skipped_already": skipped,
        "threshold_cents": LOW_BALANCE_THRESHOLD_CENTS,
    }


def _broadcast_alert(customer: Customer, wallet: CustomerWallet) -> None:
    try:
        from app.services.websocket_manager import manager as ws_manager
        asyncio.run(ws_manager.broadcast({
            "type": "low_balance_alert",
            "customer_id": customer.id,
            "balance_cents": wallet.balance_cents,
            "threshold_cents": LOW_BALANCE_THRESHOLD_CENTS,
        }))
    except Exception as e:
        logger.warning(f"low-balance WS broadcast failed for {customer.id}: {e}")


def _send_via_main_account_best_effort(customer: Customer, wallet: CustomerWallet) -> None:
    """Saved-Messages notification when the customer has a main account bound."""
    if not customer.main_account_id:
        return
    try:
        from app.models.account import Account
        from app.services.main_account_notifier import _send_via_main_account
        with Session(engine) as s:
            main = s.get(Account, customer.main_account_id)
            if not main:
                return
        body = (
            f"⚠️ TG1 Bulk Send — wallet running low\n\n"
            f"Balance: ${wallet.balance_cents / 100:.2f} "
            f"(threshold: ${LOW_BALANCE_THRESHOLD_CENTS / 100:.0f})\n\n"
            f"Top up to keep your running batches sending."
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_send_via_main_account(main, body))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as e:
        logger.warning(f"low-balance main-account send failed for {customer.id}: {e}")
