"""
Customer-facing monitor rules (S2.2).

Mounted at /customer/monitors. The customer (Customer JWT) authors keyword
monitor rules that fire only on TG accounts assigned to that customer. The
listener applies a tenant filter so cross-customer accounts never trigger
each other's rules.

`marketing_mode='active'` is allowed but force-pairs with
`reply_mode='group_reply'` — same half-automatic safety rule as
sales-owned monitors. The DM decision stays with humans (either the
customer's own sales seat or the customer themselves through the
takeover flow). Customers requiring full auto-DM must contact admin.

Customer-owned rules also require the `ai_marketing_assistant` feature
to be enabled on the customer's account; see S2.3 for the gate.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.keyword_monitor import (
    KeywordMonitor, KeywordMonitorCreate, KeywordMonitorRead,
    KeywordMonitorUpdate, KeywordHit, KeywordHitRead,
)
from app.services import feature_billing as fb


router = APIRouter()


# Same cap as sales-owned active rules (sales_monitors.SALES_ACTIVE_MODE_DAILY_LIMIT).
CUSTOMER_ACTIVE_MODE_DAILY_LIMIT = 20

AI_MARKETING_FEATURE_SLUG = "ai_marketing_assistant"


def _enforce_customer_mode_rules(
    marketing_mode: Optional[str],
    reply_mode: Optional[str],
) -> None:
    """Customer-owned active rules may post into the source group but
    never auto-DM users."""
    if marketing_mode == "active" and reply_mode == "private_dm":
        raise HTTPException(
            status_code=400,
            detail="marketing_mode='active' + reply_mode='private_dm' "
                   "is not allowed for customer-owned monitors; use "
                   "reply_mode='group_reply' and let your sales seat "
                   "take over the DM manually.",
        )


def _require_ai_marketing_enabled(session: Session, customer_id: int) -> None:
    """Customer must have the ai_marketing_assistant feature enabled. The
    feature is auto-enabled when a paid subscription is activated; see
    billing_service.activate_invoice (S2.3)."""
    try:
        fb.require_enabled(session, customer_id, AI_MARKETING_FEATURE_SLUG)
    except fb.FeatureNotEnabledError:
        raise HTTPException(
            status_code=402,
            detail=f"Feature '{AI_MARKETING_FEATURE_SLUG}' is not enabled "
                   "on your account. Activate a subscription that includes "
                   "the AI marketing assistant, or contact support.",
        )


def _own_or_404(
    session: Session, customer: Customer, monitor_id: int,
) -> KeywordMonitor:
    mon = session.get(KeywordMonitor, monitor_id)
    if not mon or mon.customer_id != customer.id:
        # Don't leak whether the id exists across tenants.
        raise HTTPException(status_code=404, detail="monitor not found")
    return mon


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("", response_model=List[KeywordMonitorRead])
def list_my_monitors(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    is_active: Optional[bool] = Query(None),
) -> Any:
    stmt = select(KeywordMonitor).where(KeywordMonitor.customer_id == customer.id)
    if is_active is not None:
        stmt = stmt.where(KeywordMonitor.is_active == is_active)
    rows = session.exec(stmt.order_by(KeywordMonitor.created_at.desc())).all()
    return rows


@router.post("", response_model=KeywordMonitorRead, status_code=201)
def create_monitor(
    payload: KeywordMonitorCreate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Create a customer-owned monitor rule. Auto-tagged with the caller.

    Requires `ai_marketing_assistant` feature enabled. Requires
    `target_groups` set (no monitoring the entire firehose).
    `marketing_mode='active'` is OK only with `reply_mode='group_reply'`.
    """
    if not payload.keyword.strip():
        raise HTTPException(status_code=400, detail="keyword is required")
    if not (payload.target_groups and payload.target_groups.strip()):
        raise HTTPException(
            status_code=400,
            detail="target_groups is required for customer-owned monitors",
        )
    _require_ai_marketing_enabled(session, customer.id)
    _enforce_customer_mode_rules(payload.marketing_mode, payload.reply_mode)

    # Strip caller-supplied ownership fields — we pin them.
    data = payload.model_dump(exclude={
        "created_by_sales_user_id", "created_by_sales_kind", "customer_id",
    })
    data["customer_id"] = customer.id
    data["created_by_sales_user_id"] = None
    data["created_by_sales_kind"] = None
    if data.get("marketing_mode") == "active":
        existing_cap = data.get("max_replies_per_day")
        if not existing_cap or existing_cap > CUSTOMER_ACTIVE_MODE_DAILY_LIMIT:
            data["max_replies_per_day"] = CUSTOMER_ACTIVE_MODE_DAILY_LIMIT

    mon = KeywordMonitor(**data)
    session.add(mon)
    session.commit()
    session.refresh(mon)
    return mon


@router.get("/{monitor_id}", response_model=KeywordMonitorRead)
def get_monitor(
    monitor_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    return _own_or_404(session, customer, monitor_id)


@router.put("/{monitor_id}", response_model=KeywordMonitorRead)
def update_monitor(
    monitor_id: int,
    payload: KeywordMonitorUpdate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    mon = _own_or_404(session, customer, monitor_id)
    effective_mm = payload.marketing_mode if payload.marketing_mode is not None else mon.marketing_mode
    effective_rm = payload.reply_mode if payload.reply_mode is not None else mon.reply_mode
    _enforce_customer_mode_rules(effective_mm, effective_rm)
    for k, v in payload.model_dump(exclude_unset=True).items():
        # Never let the customer reassign tenant via update.
        if k == "customer_id":
            continue
        setattr(mon, k, v)
    if mon.marketing_mode == "active":
        if not mon.max_replies_per_day or mon.max_replies_per_day > CUSTOMER_ACTIVE_MODE_DAILY_LIMIT:
            mon.max_replies_per_day = CUSTOMER_ACTIVE_MODE_DAILY_LIMIT
    session.add(mon)
    session.commit()
    session.refresh(mon)
    return mon


@router.delete("/{monitor_id}")
def delete_monitor(
    monitor_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    mon = _own_or_404(session, customer, monitor_id)
    session.delete(mon)
    session.commit()
    return {"deleted": monitor_id}


@router.get("/{monitor_id}/recent-hits", response_model=List[KeywordHitRead])
def list_recent_hits(
    monitor_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """Recent KeywordHit rows for this monitor (newest first), for tuning."""
    _own_or_404(session, customer, monitor_id)
    rows = session.exec(
        select(KeywordHit)
        .where(KeywordHit.keyword_monitor_id == monitor_id)
        .order_by(KeywordHit.detected_at.desc())
        .limit(limit)
    ).all()
    return rows
