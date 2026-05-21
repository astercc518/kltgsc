"""
Admin endpoint for crediting platform-sales wallets (Epic C2).

Platform sales (User.role='sales') don't self-topup via USDT — admin
grants them viewing budget directly. Mounted at /admin/sales-wallet.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.sales_wallet import (
    OWNER_PLATFORM_SALES,
    SalesWallet, SalesWalletRead, SalesWalletTransactionRead,
)
from app.models.user import User
from app.services import sales_wallet_service as svc


router = APIRouter()


class CreditPlatformSalesRequest(BaseModel):
    user_id: int = Field(description="User.id of the platform sales user")
    amount_usd: float = Field(gt=0, le=10000)
    description: str = Field(default="admin credit", max_length=200)


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not (user.is_superuser or getattr(user, "role", None) == "admin"):
        raise HTTPException(status_code=403, detail="admin only")
    return user


@router.post("/credit")
def credit_platform_sales(
    payload: CreditPlatformSalesRequest,
    admin: User = Depends(_require_admin),
    session: Session = Depends(get_session),
) -> Any:
    target = session.get(User, payload.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if not (target.is_superuser or getattr(target, "role", None) == "sales"):
        raise HTTPException(status_code=400, detail="user is not a sales/admin")

    amount_cents = int(round(payload.amount_usd * 100))
    idem = f"admin-credit-platform-sales:{target.id}:{admin.id}:{payload.amount_usd}"

    try:
        txn = svc.admin_credit_platform_sales(
            session, user_id=target.id, amount_cents=amount_cents,
            description=f"{payload.description} (by admin {admin.username})",
            idempotency_key=idem,
        )
    except svc.SalesWalletError as e:
        raise HTTPException(status_code=400, detail=str(e))

    wallet = svc.get_or_create_wallet(session, OWNER_PLATFORM_SALES, target.id)
    return {
        "ok": True,
        "user_id": target.id,
        "credited_cents": amount_cents,
        "balance_after": wallet.balance_cents,
        "txn_id": txn.id,
    }


@router.get("/wallets", response_model=List[SalesWalletRead])
def list_platform_wallets(
    admin: User = Depends(_require_admin),
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> Any:
    return session.exec(
        select(SalesWallet)
        .where(SalesWallet.owner_type == OWNER_PLATFORM_SALES)
        .order_by(SalesWallet.balance_cents.desc())
        .offset(skip).limit(limit)
    ).all()
