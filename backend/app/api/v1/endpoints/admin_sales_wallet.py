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


# ── Phase F3 — bulk monthly credit + performance report ─────────────────


class BulkCreditRequest(BaseModel):
    amount_usd: float = Field(gt=0, le=1000,
        description="amount to credit each platform sales user this run")
    description: str = Field(default="monthly budget", max_length=200)
    period_tag: str = Field(...,
        description="unique tag for idempotency, e.g. '2026-05' — re-running with the same tag is a no-op")
    only_active: bool = Field(default=True,
        description="skip users with is_active=false")


@router.post("/bulk-monthly-credit")
def bulk_monthly_credit(
    payload: BulkCreditRequest,
    admin: User = Depends(_require_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Top up every platform_sales user's wallet in one call. Idempotent
    on (period_tag, user_id) — re-running for the same period is a no-op,
    so it's safe to schedule a cron or trigger this multiple times."""
    targets = session.exec(
        select(User).where(User.role == "sales")
    ).all()
    if payload.only_active:
        targets = [u for u in targets if u.is_active]

    amount_cents = int(round(payload.amount_usd * 100))
    credited: list[dict] = []
    skipped: list[dict] = []
    for u in targets:
        idem = f"bulk-monthly:{payload.period_tag}:{u.id}"
        try:
            txn = svc.admin_credit_platform_sales(
                session, user_id=u.id, amount_cents=amount_cents,
                description=f"{payload.description} (period {payload.period_tag}) by admin {admin.username}",
                idempotency_key=idem,
            )
            credited.append({
                "user_id": u.id, "username": u.username,
                "amount_cents": amount_cents,
                "txn_id": txn.id, "balance_after_cents": txn.balance_after_cents,
            })
        except svc.SalesWalletError as e:
            skipped.append({"user_id": u.id, "reason": str(e)})

    return {
        "ok": True,
        "period_tag": payload.period_tag,
        "credited_count": len(credited),
        "skipped_count": len(skipped),
        "credited": credited,
        "skipped": skipped,
    }


@router.get("/performance")
def sales_performance(
    _admin: User = Depends(_require_admin),
    session: Session = Depends(get_session),
    days: int = 30,
) -> Any:
    """Per-platform-sales rollup: spend (charged_cents) / claimed lead count
    / converted lead count over the last `days` days. Used by BusinessOps
    SalesPerformancePanel."""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models.lead import Lead
    from app.models.sales_wallet import SalesWallet, SalesWalletTransaction, OWNER_PLATFORM_SALES

    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = []
    sales = session.exec(select(User).where(User.role == "sales")).all()

    for u in sales:
        # current balance
        wallet = session.exec(
            select(SalesWallet).where(
                SalesWallet.owner_type == OWNER_PLATFORM_SALES,
                SalesWallet.owner_id == u.id,
            )
        ).first()
        # spend (sum of negative charges in the window)
        spend_sum = session.exec(
            select(func.sum(SalesWalletTransaction.amount_cents)).where(
                SalesWalletTransaction.owner_type == OWNER_PLATFORM_SALES,
                SalesWalletTransaction.owner_id == u.id,
                SalesWalletTransaction.type == "charge",
                SalesWalletTransaction.created_at >= cutoff,
            )
        ).one() or 0
        spend_cents = abs(int(spend_sum or 0))
        # claimed leads
        claimed = session.exec(
            select(func.count(Lead.id)).where(
                Lead.assigned_to_user_id == u.id,
                Lead.claimed_at >= cutoff,
            )
        ).one()
        # converted leads
        converted = session.exec(
            select(func.count(Lead.id)).where(
                Lead.assigned_to_user_id == u.id,
                Lead.status == "converted",
                Lead.last_interaction_at >= cutoff,
            )
        ).one()
        rows.append({
            "user_id": u.id,
            "username": u.username,
            "is_active": u.is_active,
            "balance_cents": wallet.balance_cents if wallet else 0,
            "spend_cents": spend_cents,
            "claimed_count": claimed,
            "converted_count": converted,
            "conversion_pct": round(converted / claimed * 100, 1) if claimed else 0.0,
        })
    rows.sort(key=lambda r: r["converted_count"], reverse=True)
    return {"days": days, "sales": rows}


# ── Phase G — assign TG accounts to a platform sales user ───────────────


class AssignAccountsRequest(BaseModel):
    user_id: int = Field(description="platform sales user (User.id with role='sales')")
    account_ids: list[int] = Field(default_factory=list,
        description="set of Account.id to assign; replaces existing assignment")


@router.post("/assign-accounts")
def assign_accounts_to_sales(
    payload: AssignAccountsRequest,
    admin: User = Depends(_require_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Bind the given Account rows to a platform sales user. The sales user
    gets day-to-day ops rights on these accounts (join/leave groups, run
    scrapes, attach their own monitor rules). Replaces any previously
    assigned set — pass [] to unassign everything for this user.

    Accounts must already belong to an internal pool (Customer.is_internal_pool=true)
    or be unallocated. Won't reassign across pools — call the admin
    /admin/accounts reassign flow first.
    """
    from app.models.account import Account
    from app.models.customer import Customer

    target = session.get(User, payload.user_id)
    if not target or target.role != "sales":
        raise HTTPException(status_code=400, detail="target user is not a platform sales")

    # Clear previous assignments for this user
    prev = session.exec(
        select(Account).where(
            Account.assigned_to_sales_user_id == payload.user_id,
            Account.assigned_to_sales_kind == "platform",
        )
    ).all()
    for a in prev:
        a.assigned_to_sales_user_id = None
        a.assigned_to_sales_kind = None
        session.add(a)

    # Apply new assignment with validation
    assigned: list[int] = []
    skipped: list[dict] = []
    for aid in payload.account_ids:
        acc = session.get(Account, aid)
        if not acc:
            skipped.append({"account_id": aid, "reason": "not found"})
            continue
        if acc.customer_id:
            cust = session.get(Customer, acc.customer_id)
            if not cust or not cust.is_internal_pool:
                skipped.append({"account_id": aid, "reason": "not in internal pool"})
                continue
        # Accept unallocated accounts too (admin's call)
        acc.assigned_to_sales_user_id = payload.user_id
        acc.assigned_to_sales_kind = "platform"
        session.add(acc)
        assigned.append(aid)

    session.commit()
    return {
        "ok": True,
        "user_id": payload.user_id,
        "username": target.username,
        "assigned_count": len(assigned),
        "assigned_account_ids": assigned,
        "skipped": skipped,
    }


@router.get("/assignments")
def list_assignments(
    _admin: User = Depends(_require_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Per-sales-user account-assignment summary for the admin UI."""
    from sqlalchemy import func
    from app.models.account import Account

    rows = session.exec(
        select(
            Account.assigned_to_sales_user_id,
            func.count(Account.id),
        )
        .where(Account.assigned_to_sales_kind == "platform")
        .group_by(Account.assigned_to_sales_user_id)
    ).all()
    by_user = {uid: cnt for uid, cnt in rows if uid is not None}

    sales = session.exec(select(User).where(User.role == "sales")).all()
    return {
        "sales": [
            {
                "user_id": u.id,
                "username": u.username,
                "is_active": u.is_active,
                "assigned_account_count": by_user.get(u.id, 0),
            }
            for u in sales
        ],
    }
