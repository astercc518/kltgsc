"""
Customer-facing wallet endpoints (TG Bulk Send W1).

Flow:
    POST /customer/wallet/topup            — start a topup (returns USDT invoice)
    GET  /customer/wallet                  — current balance + totals
    GET  /customer/wallet/transactions     — paginated transaction history

The actual balance credit happens after payment confirmation via
NowPayments webhook (Epic 2.5) or admin manual confirmation.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.subscription import InvoiceRead
from app.models.wallet import (
    WalletRead, WalletTransactionRead,
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
