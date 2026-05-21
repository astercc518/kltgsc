"""
Epic 2.5 — Payment gateway webhooks.

Currently supports:
  • POST /webhooks/nowpayments  (HMAC-SHA512 signature verification)

The endpoint is a no-op if NOWPAYMENTS_IPN_SECRET is not configured (returns
503). This makes the existing admin-manual flow the default until ops sets up
a NowPayments account and points its IPN URL here.

Body shape (from NowPayments docs):
  {
    "payment_id": 1234567,
    "payment_status": "confirmed" | "partially_paid" | "finished" | ...,
    "pay_address": "T...",
    "price_amount": 299.0,
    "price_currency": "usd",
    "pay_amount": 299.34,
    "pay_currency": "usdttrc20",
    "order_id": "tg1-invoice-42",       <- we set this to "tg1-invoice-{invoice_id}"
    "order_description": "TG1.AI Growth Plan - Monthly",
    "outcome_amount": 298.5,
    "outcome_currency": "usdttrc20",
    ...
  }
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from datetime import datetime

from app.core.config import settings
from app.core.db import get_session
from app.models.subscription import INV_PAID, INV_PENDING, Invoice
from app.services.billing_service import BillingError, activate_invoice
from app.services.wallet_service import (
    WALLET_TOPUP_PLAN, WalletError, credit_wallet_from_invoice,
)
from app.services.sales_wallet_service import (
    SALES_WALLET_TOPUP_PLAN,
    SalesWalletError,
    credit_sales_wallet_from_invoice,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Statuses NowPayments uses to signal a successful, final payment
# (others like 'waiting', 'partially_paid' should NOT activate)
_NOWPAYMENTS_PAID_STATUSES = {"finished", "confirmed"}


def _verify_nowpayments_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """NowPayments signs the raw JSON body with HMAC-SHA512 keyed by IPN_SECRET.

    The signed payload is the JSON with keys sorted alphabetically and no spaces.
    We re-canonicalize to match.
    """
    try:
        parsed = json.loads(raw_body)
        canonical = json.dumps(parsed, separators=(",", ":"), sort_keys=True)
    except json.JSONDecodeError:
        return False
    expected = hmac.new(
        secret.encode(), canonical.encode(), hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature.lower().strip())


def _extract_invoice_id(order_id: str | None) -> int | None:
    """Our convention: order_id = 'tg1-invoice-{id}'. Anything else -> None."""
    if not order_id:
        return None
    parts = order_id.split("-")
    if len(parts) != 3 or parts[0] != "tg1" or parts[1] != "invoice":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


@router.post("/nowpayments")
async def nowpayments_webhook(
    request: Request,
    x_nowpayments_sig: str = Header(default="", alias="x-nowpayments-sig"),
    session: Session = Depends(get_session),
) -> Any:
    """Receive payment notification from NowPayments and auto-activate."""
    if not settings.NOWPAYMENTS_IPN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NowPayments webhook not configured (NOWPAYMENTS_IPN_SECRET unset)",
        )

    raw = await request.body()

    if not _verify_nowpayments_signature(raw, x_nowpayments_sig, settings.NOWPAYMENTS_IPN_SECRET):
        logger.warning(
            "nowpayments_webhook: invalid signature (body_len=%d, sig_provided=%s)",
            len(raw), bool(x_nowpayments_sig),
        )
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    payment_status = (payload.get("payment_status") or "").lower()
    tx_hash = (payload.get("payin_hash") or payload.get("outcome_hash")
               or f"np-{payload.get('payment_id', 'unknown')}")

    invoice_id = _extract_invoice_id(payload.get("order_id"))
    if invoice_id is None:
        logger.warning("nowpayments_webhook: unrecognized order_id=%r", payload.get("order_id"))
        return {"status": "ignored", "reason": "unrecognized order_id"}

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        logger.warning("nowpayments_webhook: invoice %s not found", invoice_id)
        return {"status": "ignored", "reason": "invoice not found"}

    # Only act on terminal-success statuses; let NowPayments keep retrying
    # intermediates without us flipping things.
    if payment_status not in _NOWPAYMENTS_PAID_STATUSES:
        logger.info(
            "nowpayments_webhook: invoice %s status=%s — no action",
            invoice.id, payment_status,
        )
        return {"status": "noop", "payment_status": payment_status}

    if invoice.status == INV_PAID:
        # Already activated (e.g. admin already confirmed manually, or webhook
        # delivered twice). Return 200 so NowPayments stops retrying.
        return {"status": "already_paid", "invoice_id": invoice.id}

    if invoice.status != INV_PENDING:
        logger.warning(
            "nowpayments_webhook: invoice %s in unexpected status %s",
            invoice.id, invoice.status,
        )
        return {"status": "rejected", "invoice_status": invoice.status}

    # Route by invoice.plan: wallet topup vs sales topup vs subscription
    if invoice.plan in (WALLET_TOPUP_PLAN, SALES_WALLET_TOPUP_PLAN):
        # Mark invoice paid, then credit the correct wallet (idempotent on invoice.id).
        invoice.status = INV_PAID
        invoice.tx_hash = tx_hash
        invoice.paid_at = datetime.utcnow()
        session.add(invoice)
        session.commit()

        try:
            if invoice.plan == SALES_WALLET_TOPUP_PLAN:
                txn = credit_sales_wallet_from_invoice(session, invoice)
            else:
                txn = credit_wallet_from_invoice(session, invoice)
        except (WalletError, SalesWalletError) as e:
            logger.error("nowpayments_webhook: wallet credit failed for invoice %s: %s",
                         invoice.id, e)
            raise HTTPException(status_code=400, detail=str(e))

        logger.info(
            "nowpayments_webhook: invoice %s -> %s credited %d cents (txn %s)",
            invoice.id, invoice.plan, txn.amount_cents, txn.id,
        )
        return {
            "status": "wallet_credited",
            "invoice_id": invoice.id,
            "txn_id": txn.id,
            "amount_cents": txn.amount_cents,
            "balance_after_cents": txn.balance_after_cents,
        }

    # Subscription plan — original flow
    try:
        subscription = activate_invoice(
            session, invoice=invoice, tx_hash=tx_hash, admin_user_id=None,
        )
    except BillingError as e:
        logger.error("nowpayments_webhook: activation failed for invoice %s: %s",
                     invoice.id, e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "nowpayments_webhook: invoice %s -> subscription %s activated automatically",
        invoice.id, subscription.id,
    )
    return {
        "status": "activated",
        "invoice_id": invoice.id,
        "subscription_id": subscription.id,
        "plan": subscription.plan,
    }
