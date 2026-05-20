"""
Admin-facing billing endpoints (Epic 2 MVP).

Used by ops to manually confirm USDT payments and activate subscriptions.
Future Epic 2.5 will add an automated webhook from a USDT gateway (e.g.
NowPayments) — see [[project-payment-decision]].
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import get_current_admin
from app.core.db import get_session
from app.models.customer import Customer, CustomerRead
from app.models.subscription import (
    ActivateSubscriptionRequest,
    Invoice,
    InvoiceRead,
    SubscriptionRead,
)
from app.models.user import User
from app.services.billing_service import BillingError, activate_invoice
from app.services.allocation_service import (
    allocate_accounts_for_customer,
    allocate_groups_for_customer,
)


router = APIRouter()


@router.get("/customers", response_model=List[CustomerRead])
def list_customers(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    status_filter: str | None = Query(None, alias="status"),
    plan_filter: str | None = Query(None, alias="plan"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    """List all customers (admin only)."""
    stmt = select(Customer)
    if status_filter:
        stmt = stmt.where(Customer.status == status_filter)
    if plan_filter:
        stmt = stmt.where(Customer.plan == plan_filter)
    rows = session.exec(
        stmt.order_by(Customer.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [CustomerRead.model_validate(r.model_dump()) for r in rows]


@router.get("/invoices", response_model=List[InvoiceRead])
def list_all_invoices(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
    status_filter: str | None = Query(None, alias="status"),
    customer_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    """List invoices across all customers (admin only).

    Common use: status=pending to find invoices needing confirmation.
    """
    stmt = select(Invoice)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    rows = session.exec(
        stmt.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [InvoiceRead.model_validate(r.model_dump()) for r in rows]


@router.post(
    "/customers/{customer_id}/activate-subscription",
    response_model=SubscriptionRead,
)
def activate_subscription(
    customer_id: int,
    payload: ActivateSubscriptionRequest,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Confirm an on-chain USDT transfer and activate the subscription.

    Ops workflow:
      1. Customer transfers USDT to the address shown in their invoice
      2. Ops sees the tx on chain explorer, copies tx_hash
      3. Ops calls this endpoint with invoice_id + tx_hash
      4. Service marks invoice paid, activates subscription, sets quota

    Idempotent: calling again for an already-paid invoice returns the
    same subscription without side effects.
    """
    invoice = session.get(Invoice, payload.invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.customer_id != customer_id:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice {invoice.id} does not belong to customer {customer_id}",
        )

    try:
        subscription = activate_invoice(
            session,
            invoice=invoice,
            tx_hash=payload.tx_hash,
            admin_user_id=admin.id,
        )
    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SubscriptionRead.model_validate(subscription.model_dump())


# ──────────────────────────────────────────────────────────────────────────
# Epic 3 — manual reallocation endpoints
# ──────────────────────────────────────────────────────────────────────────

@router.post("/customers/{customer_id}/reallocate-accounts")
def reallocate_accounts(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Top up the customer's allocated accounts to quota (idempotent).

    Use when activation-time provisioning failed or quota was bumped.
    """
    from app.models.customer import Customer
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    result = allocate_accounts_for_customer(session, customer)
    return {
        "allocated": len(result.accounts),
        "customized": result.customized,
        "industry": result.industry,
        "account_ids": [a.id for a in result.accounts],
    }


@router.post("/customers/{customer_id}/reallocate-groups")
def reallocate_groups(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Top up the customer's allocated source groups to quota (best-effort)."""
    from app.models.customer import Customer
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    result = allocate_groups_for_customer(session, customer)
    return {
        "allocated": len(result.groups),
        "industry_pool_size": result.pool_size,
        "industry": result.industry,
        "group_ids": [g.id for g in result.groups],
    }


@router.post("/customers/{customer_id}/regenerate-kb")
def regenerate_kb(
    customer_id: int,
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Wipe + regenerate the customer's auto industry KB.

    Use when customer changes industry or KB prompts are upgraded. Returns
    counts; the actual KB rows are visible via /customer/knowledge-bases.
    """
    from app.models.customer import Customer
    from app.services.industry_kb_service import regenerate_kb_for_customer
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    result = regenerate_kb_for_customer(session, customer)
    return {
        "industry": result.industry,
        "created": len(result.created),
        "embedded": result.embedded,
        "skipped": result.skipped,
        "kb_ids": [k.id for k in result.created],
    }
