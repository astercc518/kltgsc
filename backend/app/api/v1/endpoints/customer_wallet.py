"""
Customer-facing wallet endpoints (TG Bulk Send W1).

Flow:
    POST /customer/wallet/topup            — start a topup (returns USDT invoice)
    GET  /customer/wallet                  — current balance + totals
    GET  /customer/wallet/transactions     — paginated transaction history
    GET  /customer/wallet/report           — monthly spend rolled up by source
    GET  /customer/wallet/report.csv       — same data as CSV

The actual balance credit happens after payment confirmation via
NowPayments webhook (Epic 2.5) or admin manual confirmation.
"""
import csv
import io
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.subscription import InvoiceRead
from app.models.wallet import (
    TXN_CHARGE, TXN_TOPUP,
    WalletRead, WalletTransaction, WalletTransactionRead,
    WalletTopupRequest, WalletTopupResponse,
    calculate_bonus_pct,
)
from app.services.wallet_service import (
    WalletError,
    create_topup_invoice,
    get_or_create_wallet,
    list_transactions,
)


router = APIRouter()


@router.post("/topup", response_model=WalletTopupResponse, status_code=201)
def topup(
    payload: WalletTopupRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Create a pending USDT invoice for wallet topup.

    Returns the invoice details + bonus info. Customer transfers the exact
    amount to payment_address. Once confirmed (webhook or admin), the wallet
    is credited with amount + bonus.

    Tiered bonus:
        $100   → 0%
        $500   → 2%
        $1000  → 5%
        $5000+ → 10%
    """
    try:
        invoice, bonus_pct, bonus_cents = create_topup_invoice(
            session, customer,
            amount_usd=payload.amount_usd,
            network=payload.network,
        )
    except WalletError as e:
        raise HTTPException(status_code=400, detail=str(e))

    final_credit_cents = int(round(payload.amount_usd * 100)) + bonus_cents

    return WalletTopupResponse(
        invoice_id=invoice.id,
        amount_usd=payload.amount_usd,
        amount_crypto=invoice.amount_crypto,
        bonus_pct=bonus_pct,
        bonus_cents=bonus_cents,
        final_credit_cents=final_credit_cents,
        currency=invoice.currency,
        network=invoice.network,
        payment_address=invoice.payment_address,
        expires_at=invoice.expires_at,
    )


@router.get("", response_model=WalletRead)
def get_wallet(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Return the customer's wallet (auto-provisioned on first access)."""
    wallet = get_or_create_wallet(session, customer.id)
    return WalletRead.model_validate(wallet.model_dump())


@router.get("/transactions", response_model=List[WalletTransactionRead])
def get_transactions(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    type_filter: Optional[str] = Query(None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """Paginated transaction history (newest first).

    Filter by type: topup | charge | refund | adjust
    """
    rows = list_transactions(
        session, customer.id,
        type_filter=type_filter, skip=skip, limit=limit,
    )
    return [WalletTransactionRead.model_validate(r.model_dump()) for r in rows]


# ── Monthly report (by source rollup + CSV export) ─────────────────────


_SOURCE_RULES = (
    # (idempotency_key prefix, source bucket).  Longest-first; the matcher
    # uses startswith() so order matters when prefixes nest.
    ("feat:scrape_group_members", "scrape"),
    ("feat:bulk_send_message", "bulk_send"),
    ("feat:bulk_invite", "invite"),
    ("feat:auto_reply_ai", "ai_marketing"),
    ("feat:ai_marketing_group_reply", "ai_marketing"),
    ("feat:ai_marketing_lead_created", "ai_marketing"),
    ("scrape-batch:", "scrape"),
    ("bulk-target-", "bulk_send"),
    ("feat:", "other_feature"),
)


def _classify_source(idempotency_key: str) -> str:
    for prefix, bucket in _SOURCE_RULES:
        if idempotency_key.startswith(prefix):
            return bucket
    return "other"


def _parse_month(month: str) -> tuple[datetime, datetime]:
    """'YYYY-MM' → (start_of_month, start_of_next_month).  Raises 400."""
    try:
        start = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@router.get("/report")
def get_wallet_report(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    month: str = Query(..., description="YYYY-MM"),
) -> Any:
    """Monthly wallet spend report.

    Rolls up `charge`-type transactions by source bucket (scrape / bulk_send /
    invite / ai_marketing / ...) inferred from `idempotency_key`, plus a daily
    series of topup-vs-charge totals.  Returns absolute charge amounts in cents
    (positive numbers represent money spent).
    """
    start, end = _parse_month(month)

    rows = session.exec(
        select(WalletTransaction)
        .where(
            WalletTransaction.customer_id == customer.id,
            WalletTransaction.created_at >= start,
            WalletTransaction.created_at < end,
        )
        .order_by(WalletTransaction.created_at.asc())
    ).all()

    by_source: dict[str, int] = {
        "scrape": 0, "bulk_send": 0, "invite": 0,
        "ai_marketing": 0, "other_feature": 0, "other": 0,
    }
    by_day: dict[str, dict[str, int]] = {}
    topup_total = 0
    charge_total = 0

    for txn in rows:
        day = txn.created_at.strftime("%Y-%m-%d")
        bucket = by_day.setdefault(day, {"topup": 0, "charge": 0})
        if txn.type == TXN_TOPUP:
            bucket["topup"] += txn.amount_cents
            topup_total += txn.amount_cents
        elif txn.type == TXN_CHARGE:
            amt = abs(txn.amount_cents)
            bucket["charge"] += amt
            charge_total += amt
            source = _classify_source(txn.idempotency_key)
            by_source[source] = by_source.get(source, 0) + amt

    return {
        "month": month,
        "by_source": by_source,
        "by_day": [{"date": d, **v} for d, v in sorted(by_day.items())],
        "topup_total_cents": topup_total,
        "charge_total_cents": charge_total,
        "txn_count": len(rows),
    }


@router.get("/report.csv")
def get_wallet_report_csv(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    month: str = Query(..., description="YYYY-MM"),
):
    """Same month window as /report, but every transaction emitted as CSV."""
    start, end = _parse_month(month)

    rows = session.exec(
        select(WalletTransaction)
        .where(
            WalletTransaction.customer_id == customer.id,
            WalletTransaction.created_at >= start,
            WalletTransaction.created_at < end,
        )
        .order_by(WalletTransaction.created_at.asc())
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "created_at_utc", "type", "source",
        "amount_cents", "balance_after_cents",
        "description", "idempotency_key",
    ])
    for txn in rows:
        writer.writerow([
            txn.id,
            txn.created_at.isoformat(timespec="seconds") + "Z",
            txn.type,
            _classify_source(txn.idempotency_key) if txn.type == TXN_CHARGE else txn.type,
            txn.amount_cents,
            txn.balance_after_cents,
            txn.description,
            txn.idempotency_key,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="wallet-{customer.id}-{month}.csv"',
        },
    )
