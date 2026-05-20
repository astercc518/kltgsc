"""
Customer-facing feature endpoints.

Routes (mounted at /api/v1/customer/features):
    GET  /customer/features                       — list features I have access to (with my pricing)
    POST /customer/features/{slug}/estimate       — cost preview (per units)
    GET  /customer/usage                          — my own usage summary
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.feature import (
    CustomerFeatureRead, EstimateCostRequest, EstimateCostResponse,
    FeatureRegistry, FeatureUsageSummary,
)
from app.models.wallet import WalletTransaction, TXN_CHARGE
from app.services import feature_billing as fb
from app.services.wallet_service import get_balance_cents


router = APIRouter()


@router.get("", response_model=List[CustomerFeatureRead])
def customer_list_features(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """List all features and customer's resolved enabled/price."""
    rows = fb.list_customer_features(session, customer.id)
    return [CustomerFeatureRead.model_validate(r) for r in rows]


@router.post("/{slug}/estimate", response_model=EstimateCostResponse)
def customer_estimate_cost(
    slug: str,
    body: EstimateCostRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Pre-flight: returns total cost + whether customer can afford it.

    Frontend should call this when user sets up a batch (units = expected count)
    and use can_afford to gate the submit button.
    """
    try:
        unit_price = fb.get_unit_price_cents(session, customer.id, slug)
    except fb.UnknownFeatureError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total = unit_price * body.units
    balance = get_balance_cents(session, customer.id)
    enabled = fb.is_enabled(session, customer.id, slug)

    return EstimateCostResponse(
        feature_slug=slug,
        units=body.units,
        unit_price_cents=unit_price,
        total_cost_cents=total,
        can_afford=enabled and balance >= total,
        balance_cents=balance,
    )


@router.get("/usage", response_model=List[FeatureUsageSummary])
def customer_get_usage(
    days: int = Query(30, ge=1, le=365),
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Customer's own usage aggregated by feature (last N days)."""
    since = datetime.utcnow() - timedelta(days=days)

    rows = session.exec(
        select(WalletTransaction).where(
            WalletTransaction.customer_id == customer.id,
            WalletTransaction.type == TXN_CHARGE,
            WalletTransaction.created_at >= since,
        ).order_by(WalletTransaction.created_at.desc())
    ).all()

    buckets: dict[str, dict] = {}
    for txn in rows:
        if not txn.idempotency_key.startswith("feat:"):
            continue
        parts = txn.idempotency_key.split(":", 2)
        if len(parts) < 2:
            continue
        slug = parts[1]

        b = buckets.setdefault(slug, {
            "feature_slug": slug,
            "name_zh": slug,
            "units_consumed": 0,
            "total_charged_cents": 0,
            "last_charged_at": None,
        })
        b["total_charged_cents"] += abs(txn.amount_cents)
        reg = session.get(FeatureRegistry, slug)
        if reg:
            b["name_zh"] = reg.name_zh
            unit = fb.get_unit_price_cents(session, customer.id, slug)
            if unit > 0:
                b["units_consumed"] += abs(txn.amount_cents) // unit
        if b["last_charged_at"] is None or txn.created_at > b["last_charged_at"]:
            b["last_charged_at"] = txn.created_at

    return [FeatureUsageSummary.model_validate(b) for b in sorted(
        buckets.values(), key=lambda x: -x["total_charged_cents"]
    )]
