"""
Customer-facing billing endpoints (Epic 2).

Flow:
    POST /customer/subscribe        — start a new subscription (returns invoice)
    GET  /customer/invoices         — list customer's invoices
    GET  /customer/invoices/{id}    — fetch a single invoice (poll for status=paid)
    GET  /customer/subscription     — get current active subscription (404 if none)
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.subscription import (
    Invoice,
    InvoiceRead,
    SubscribeRequest,
    Subscription,
    SubscriptionRead,
)
from app.services.billing_service import (
    BillingError,
    create_pending_invoice,
    get_active_subscription,
)


router = APIRouter()


@router.post("/subscribe", response_model=InvoiceRead, status_code=201)
def subscribe(
    payload: SubscribeRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Start a subscription. Returns a pending USDT invoice.

    The client should display invoice.payment_address and invoice.amount_crypto
    to the customer. After they transfer USDT, ops will manually confirm via
    /admin/customers/{id}/activate-subscription.

    If the customer already has an in-flight pending invoice for the same
    plan + network, that invoice is returned instead of creating a new one
    (idempotent).
    """
    try:
        invoice = create_pending_invoice(
            session, customer, plan=payload.plan, network=payload.network
        )
    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return InvoiceRead.model_validate(invoice.model_dump())


@router.get("/invoices", response_model=List[InvoiceRead])
def list_invoices(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List the customer's invoices (most recent first)."""
    stmt = select(Invoice).where(Invoice.customer_id == customer.id)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    rows = session.exec(
        stmt.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [InvoiceRead.model_validate(r.model_dump()) for r in rows]


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Fetch a single invoice — client polls this to detect status=paid."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceRead.model_validate(invoice.model_dump())


@router.get("/subscription", response_model=SubscriptionRead)
def get_subscription(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Get the customer's current active subscription. 404 if none."""
    sub = get_active_subscription(session, customer.id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription",
        )
    return SubscriptionRead.model_validate(sub.model_dump())
