"""
Sales-facing lead inbox endpoints (Epic D + E backend).

Mounted at /sales/leads. Accepts either customer_sales JWT (tenant-scoped
to customer_id) or platform sales (User.role='sales', see all customers).

The key behavioral change vs /api/v1/leads is per-view billing: opening
a lead's full detail charges the sales user's personal SalesWallet
(LEAD_VIEW_PRICE_CENTS = 50¢ by default). The list view returns
contact-masked rows so salespeople can shop before paying. Same sales
user viewing the same lead twice on the same UTC date is idempotent —
they pay once, then re-view freely.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps_sales import SalesContext, get_current_sales
from app.core.db import get_session
from app.models.customer_user import CustomerUser
from app.models.lead import Lead, LeadInteraction
from app.models.sales_wallet import OWNER_CUSTOMER_SALES, OWNER_PLATFORM_SALES
from app.services import sales_wallet_service as swsvc


router = APIRouter()


# Default 50¢ per view; can override via env without code/redeploy.
LEAD_VIEW_PRICE_CENTS = int(os.environ.get("LEAD_VIEW_PRICE_CENTS", "50"))


# ── Schemas ────────────────────────────────────────────────────────────


class LeadCardView(BaseModel):
    """List/card view — contact info masked (no telegram id, hint only)."""
    id: int
    industry: Optional[str]
    category: Optional[str]
    source: str
    status: str
    first_name_hint: Optional[str]     # only first 1–2 chars + '…'
    username_hint: Optional[str]
    phone_hint: Optional[str]
    has_notes: bool
    view_count: int
    already_viewed_today: bool
    last_interaction_at: datetime
    created_at: datetime


class LeadFullView(BaseModel):
    """Detail view returned after successful view charge — contact unmasked."""
    id: int
    industry: Optional[str]
    category: Optional[str]
    source: str
    bulk_batch_id: Optional[int]
    status: str
    telegram_user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    view_count: int
    customer_id: Optional[int]
    account_id: int
    tags: List[str]
    last_interaction_at: datetime
    created_at: datetime
    interactions: List[dict]


class ViewChargeReceipt(BaseModel):
    lead: LeadFullView
    charged_cents: int               # 0 if already viewed today (no double charge)
    balance_after_cents: int
    charge_skipped: bool             # True when same-day re-view


# ── Helpers ────────────────────────────────────────────────────────────


def _mask_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if len(s) <= 1:
        return f"{s}*"
    return f"{s[0]}{'*' * min(len(s) - 1, 6)}"


def _mask_phone(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return f"***{s[-4:]}" if len(s) >= 4 else "***"


def _scope_to_sales(stmt, sales: SalesContext):
    """Visibility rules:
      - customer_sales → only leads of own tenant (Lead.customer_id = sales.customer_id)
      - platform_sales → only leads whose customer is flagged is_internal_pool=true
        (the company's own lead pool, never external customers' leads)
    """
    from app.models.customer import Customer
    if sales.kind == "customer":
        return stmt.where(Lead.customer_id == sales.customer_id)
    # platform_sales: subquery for internal-pool customer ids
    return stmt.where(
        Lead.customer_id.in_(
            select(Customer.id).where(Customer.is_internal_pool.is_(True))
        )
    )


def _owner_type_for(sales: SalesContext) -> str:
    return OWNER_CUSTOMER_SALES if sales.kind == "customer" else OWNER_PLATFORM_SALES


def _industry_filter_for(session: Session, sales: SalesContext) -> Optional[List[str]]:
    """Customer-sales sub-users may have a self-set industry_filter."""
    if sales.kind != "customer":
        return None
    cu = session.get(CustomerUser, sales.user_id)
    if not cu:
        return None
    arr = json.loads(cu.industry_filter_json or "[]")
    return arr if arr else None


def _already_viewed_today(
    session: Session, sales: SalesContext, lead_id: int,
) -> bool:
    from app.models.sales_wallet import SalesWalletTransaction
    today = date.today().isoformat()
    key = f"lead-view:{_owner_type_for(sales)}:{sales.user_id}:{lead_id}:{today}"
    return session.exec(
        select(SalesWalletTransaction).where(
            SalesWalletTransaction.idempotency_key == key,
        )
    ).first() is not None


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("", response_model=List[LeadCardView])
def list_leads(
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
    industry: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    stmt = select(Lead)
    stmt = _scope_to_sales(stmt, sales)
    if status:
        stmt = stmt.where(Lead.status == status)
    if source:
        stmt = stmt.where(Lead.source == source)
    if category:
        stmt = stmt.where(Lead.category == category)

    # Industry: explicit query param overrides sub-user's industry_filter.
    if industry:
        stmt = stmt.where(Lead.industry == industry)
    else:
        ifilter = _industry_filter_for(session, sales)
        if ifilter:
            stmt = stmt.where(Lead.industry.in_(ifilter))

    rows = session.exec(
        stmt.order_by(Lead.last_interaction_at.desc()).offset(skip).limit(limit)
    ).all()

    # Pre-compute viewed-today flags via batched lookup
    from app.models.sales_wallet import SalesWalletTransaction
    today = date.today().isoformat()
    owner_type = _owner_type_for(sales)
    key_prefix = f"lead-view:{owner_type}:{sales.user_id}:"
    txn_rows = session.exec(
        select(SalesWalletTransaction.idempotency_key).where(
            SalesWalletTransaction.idempotency_key.like(f"{key_prefix}%:{today}"),
        )
    ).all()
    viewed_today = {int(k.split(":")[3]) for k in txn_rows
                    if k.split(":")[-1] == today}

    return [
        LeadCardView(
            id=r.id,
            industry=r.industry,
            category=r.category,
            source=r.source,
            status=r.status,
            first_name_hint=_mask_name(r.first_name),
            username_hint=_mask_name(r.username),
            phone_hint=_mask_phone(r.phone),
            has_notes=bool(r.notes),
            view_count=r.view_count,
            already_viewed_today=(r.id in viewed_today),
            last_interaction_at=r.last_interaction_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{lead_id}/view", response_model=ViewChargeReceipt)
def view_lead(
    lead_id: int,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    """Open a lead's full detail.

    Charges LEAD_VIEW_PRICE_CENTS from the sales wallet — idempotent per
    (viewer, lead, UTC date). Returns 402 if balance insufficient.
    """
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    if sales.kind == "customer" and lead.customer_id != sales.customer_id:
        raise HTTPException(status_code=404, detail="lead not found")
    if sales.kind == "platform":
        # F1: platform_sales only opens leads belonging to an internal pool
        from app.models.customer import Customer
        owner = session.get(Customer, lead.customer_id) if lead.customer_id else None
        if not owner or not owner.is_internal_pool:
            raise HTTPException(status_code=404, detail="lead not found")

    owner_type = _owner_type_for(sales)
    today = date.today().isoformat()
    idem = f"lead-view:{owner_type}:{sales.user_id}:{lead_id}:{today}"

    # Pre-check balance (only charge if we haven't already today)
    already = _already_viewed_today(session, sales, lead_id)
    charged_cents = 0
    charge_skipped = already
    if not already:
        try:
            txn = swsvc.charge_sales(
                session,
                owner_type=owner_type, owner_id=sales.user_id,
                amount_cents=LEAD_VIEW_PRICE_CENTS,
                idempotency_key=idem,
                description=f"Lead view #{lead_id} ({sales.email})",
                lead_id=lead_id,
            )
            charged_cents = LEAD_VIEW_PRICE_CENTS
            # Bump view_count only on first-of-day view
            lead.view_count = (lead.view_count or 0) + 1
            session.add(lead)
            session.commit()
        except swsvc.InsufficientSalesBalanceError as e:
            raise HTTPException(status_code=402, detail=str(e))
        except swsvc.SalesWalletError as e:
            raise HTTPException(status_code=400, detail=str(e))

    balance = swsvc.get_balance_cents(session, owner_type, sales.user_id)

    interactions = session.exec(
        select(LeadInteraction)
        .where(LeadInteraction.lead_id == lead_id)
        .order_by(LeadInteraction.created_at.desc())
        .limit(50)
    ).all()
    inter_payload = [
        {
            "id": i.id,
            "direction": i.direction,
            "message_type": i.message_type,
            "content": i.content,
            "created_at": i.created_at.isoformat(),
        }
        for i in interactions
    ]

    return ViewChargeReceipt(
        lead=LeadFullView(
            id=lead.id,
            industry=lead.industry,
            category=lead.category,
            source=lead.source,
            bulk_batch_id=lead.bulk_batch_id,
            status=lead.status,
            telegram_user_id=lead.telegram_user_id,
            username=lead.username,
            first_name=lead.first_name,
            last_name=lead.last_name,
            phone=lead.phone,
            notes=lead.notes,
            view_count=lead.view_count,
            customer_id=lead.customer_id,
            account_id=lead.account_id,
            tags=json.loads(lead.tags_json or "[]"),
            last_interaction_at=lead.last_interaction_at,
            created_at=lead.created_at,
            interactions=inter_payload,
        ),
        charged_cents=charged_cents,
        balance_after_cents=balance,
        charge_skipped=charge_skipped,
    )


class IndustryStat(BaseModel):
    industry: str
    count: int


@router.get("/industries", response_model=List[IndustryStat])
def list_industries(
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    """Return industries with lead counts inside the sales' scope."""
    from sqlalchemy import func
    stmt = select(Lead.industry, func.count(Lead.id)).where(Lead.industry.is_not(None))
    stmt = _scope_to_sales(stmt, sales).group_by(Lead.industry)
    rows = session.exec(stmt).all()
    return [IndustryStat(industry=row[0], count=row[1]) for row in rows if row[0]]
