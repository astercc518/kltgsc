"""
Customer-scoped read endpoints — tenant-isolated views of business resources.

All queries filter by `customer_id = current_customer.id`. Rows with
customer_id IS NULL belong to the system (admin-only) and are invisible
to customers.

This is the Epic 1 MVP. Epic 3 (account customization + auto-replacement)
and Epic 4 (industry KB + group library) will add write endpoints and
richer behavior on top of this foundation.
"""
from typing import Any, List, Optional

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.account import Account, AccountRead
from app.models.customer import Customer, CustomerRead, PLAN_QUOTA
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseRead
from app.models.lead import Lead, LeadRead


router = APIRouter()


# ---------------------------------------------------------------------------
# Quota / dashboard summary
# ---------------------------------------------------------------------------

@router.get("/quota")
def get_quota_usage(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> dict:
    """Current plan, quota limits, and live usage counters.

    Used by the customer dashboard to render the quota meter.
    """
    # Live counts (authoritative — the `*_used` columns on Customer are
    # eventually consistent counters maintained by allocation flows in
    # Epic 3, but for the MVP we always reconcile from source-of-truth)
    account_count = session.exec(
        select(func.count()).select_from(Account)
        .where(Account.customer_id == customer.id)
    ).one()
    lead_count = session.exec(
        select(func.count()).select_from(Lead)
        .where(Lead.customer_id == customer.id)
    ).one()
    kb_count = session.exec(
        select(func.count()).select_from(KnowledgeBase)
        .where(KnowledgeBase.customer_id == customer.id)
    ).one()

    plan_defaults = PLAN_QUOTA.get(customer.plan or "", {})

    return {
        "plan": customer.plan,
        "status": customer.status,
        "subscription_status": customer.subscription_status,
        "current_period_end": customer.current_period_end,
        "limits": {
            "account_quota": customer.account_quota or plan_defaults.get("account", 0),
            "group_quota": customer.group_quota or plan_defaults.get("group", 0),
            "token_quota": customer.token_quota or plan_defaults.get("token", 0),
            "seat_quota": customer.seat_quota or plan_defaults.get("seat", 1),
        },
        "usage": {
            "accounts": account_count,
            "leads": lead_count,
            "knowledge_bases": kb_count,
            "tokens": customer.token_used,
        },
    }


# ---------------------------------------------------------------------------
# Tenant-scoped resource lists
# ---------------------------------------------------------------------------

@router.get("/accounts", response_model=List[AccountRead])
def list_my_accounts(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List TG accounts allocated to the current customer."""
    rows = session.exec(
        select(Account)
        .where(Account.customer_id == customer.id)
        .offset(skip).limit(limit)
    ).all()
    return rows


@router.get("/leads", response_model=List[LeadRead])
def list_my_leads(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    source: str | None = Query(None, description="Filter by lead source: monitor | bulk"),
    bulk_batch_id: int | None = Query(None, description="Filter to a specific bulk batch"),
) -> Any:
    """List leads captured for the current customer.

    Filter knobs (used by Portal /bulk/inbox to scope to bulk replies):
        - source: 'bulk' to see only bulk-send replies, 'monitor' for keyword hits
        - bulk_batch_id: narrow further to a single batch
    """
    stmt = select(Lead).where(Lead.customer_id == customer.id)
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if source:
        stmt = stmt.where(Lead.source == source)
    if bulk_batch_id is not None:
        stmt = stmt.where(Lead.bulk_batch_id == bulk_batch_id)
    rows = session.exec(
        stmt.order_by(Lead.last_interaction_at.desc()).offset(skip).limit(limit)
    ).all()
    return rows


# ─────────────────────────────────────────────────────────────────────────
# Epic 5.2 — Customer-tunable settings (handover group + timeout)
# ─────────────────────────────────────────────────────────────────────────


class CustomerSettingsUpdate(BaseModel):
    handover_group_link: Optional[str] = None
    takeover_timeout_minutes: Optional[int] = None  # 1..30
    notify_main_account: Optional[bool] = None


class CustomerSettingsRead(BaseModel):
    handover_group_link: Optional[str]
    takeover_timeout_minutes: int
    notify_main_account: bool


@router.get("/settings", response_model=CustomerSettingsRead)
def get_settings(customer: Customer = Depends(get_current_customer)) -> Any:
    return CustomerSettingsRead(
        handover_group_link=customer.handover_group_link,
        takeover_timeout_minutes=customer.takeover_timeout_minutes,
        notify_main_account=customer.notify_main_account,
    )


@router.patch("/settings", response_model=CustomerSettingsRead)
def update_settings(
    payload: CustomerSettingsUpdate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    if payload.handover_group_link is not None:
        link = payload.handover_group_link.strip()
        if link and not (link.startswith("https://t.me/") or link.startswith("tg://")):
            raise HTTPException(
                status_code=400,
                detail="handover_group_link must be a t.me or tg:// URL",
            )
        customer.handover_group_link = link or None
    if payload.takeover_timeout_minutes is not None:
        v = payload.takeover_timeout_minutes
        if not (1 <= v <= 30):
            raise HTTPException(status_code=400, detail="takeover_timeout_minutes must be 1..30")
        customer.takeover_timeout_minutes = v
    if payload.notify_main_account is not None:
        customer.notify_main_account = bool(payload.notify_main_account)
    customer.updated_at = datetime.utcnow()
    session.add(customer); session.commit(); session.refresh(customer)
    return CustomerSettingsRead(
        handover_group_link=customer.handover_group_link,
        takeover_timeout_minutes=customer.takeover_timeout_minutes,
        notify_main_account=customer.notify_main_account,
    )


@router.get("/knowledge-bases", response_model=List[KnowledgeBaseRead])
def list_my_knowledge_bases(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List knowledge-base entries owned by the current customer.

    Note: this excludes global/system KBs (customer_id IS NULL). The
    auto-generated industry KB from Epic 4 will be associated with the
    customer's industry but still tagged with their customer_id.
    """
    rows = session.exec(
        select(KnowledgeBase)
        .where(KnowledgeBase.customer_id == customer.id)
        .offset(skip).limit(limit)
    ).all()
    return rows
