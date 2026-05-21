"""
Sales wallet endpoints (Epic C2).

Mounted at /sales/wallet. Accepts both customer_sales JWT and platform
sales (admin User with role='sales') tokens, via deps_sales.get_current_sales.

For customer_sales: POST /topup creates a USDT Invoice and the
NowPayments webhook will credit on confirmation.
For platform_sales: topup is admin-only (see /admin/sales-wallet/credit).
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.api.deps_sales import SalesContext, get_current_sales
from app.core.db import get_session
from app.models.customer_user import CustomerUser
from app.models.sales_wallet import (
    OWNER_CUSTOMER_SALES,
    SalesWalletRead, SalesWalletTopupRequest, SalesWalletTransactionRead,
)
from app.models.subscription import InvoiceRead
from app.services import sales_wallet_service as svc


router = APIRouter()


@router.get("", response_model=SalesWalletRead)
def get_wallet(
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    owner_type = (OWNER_CUSTOMER_SALES if sales.kind == "customer"
                  else "platform_sales")
    wallet = svc.get_or_create_wallet(session, owner_type, sales.user_id)
    return wallet


@router.get("/transactions", response_model=List[SalesWalletTransactionRead])
def list_transactions(
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
    type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    owner_type = (OWNER_CUSTOMER_SALES if sales.kind == "customer"
                  else "platform_sales")
    return svc.list_transactions(
        session, owner_type, sales.user_id,
        type_filter=type, skip=skip, limit=limit,
    )


@router.post("/topup")
def topup(
    payload: SalesWalletTopupRequest,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    """Customer-sales tops up via USDT invoice. Platform-sales: 403 (use
    admin credit instead)."""
    if sales.kind != "customer":
        raise HTTPException(
            status_code=403,
            detail="Platform sales cannot self-topup. Ask admin to credit your wallet.",
        )
    cu = session.get(CustomerUser, sales.user_id)
    if not cu:
        raise HTTPException(status_code=404, detail="sales user not found")

    try:
        invoice, bonus_pct, bonus_cents = svc.create_topup_invoice_for_customer_sales(
            session, cu, payload.amount_usd, payload.network,
        )
    except svc.SalesWalletError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "invoice": InvoiceRead.model_validate(invoice.model_dump()),
        "bonus_pct": bonus_pct,
        "bonus_cents": bonus_cents,
        "final_credit_cents": int(round(payload.amount_usd * 100)) + bonus_cents,
    }
