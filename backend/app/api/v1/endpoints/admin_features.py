"""
Admin Feature & Customer-Feature management endpoints.

Routes (mounted at /api/v1/admin/features and /api/v1/admin/customers/{cid}/features):
    GET    /admin/features                    — list global feature registry
    GET    /admin/features/{slug}             — get one registry row
    PATCH  /admin/features/{slug}             — update default price / enabled_by_default / description
    GET    /admin/customers/{cid}/features    — list per-customer feature views (with override resolved)
    PUT    /admin/customers/{cid}/features/{slug}    — set / override customer feature
    DELETE /admin/customers/{cid}/features/{slug}    — remove override (fall back to default)
    GET    /admin/customers/{cid}/usage       — aggregate usage by feature for that customer

All endpoints require admin (get_current_admin).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func

from app.api.deps import get_current_admin
from app.core.db import get_session
from app.models.customer import Customer
from app.models.feature import (
    FeatureRegistry, FeatureRegistryRead, FeatureRegistryUpdate,
    CustomerFeature, CustomerFeatureRead, CustomerFeatureUpdate,
    FeatureUsageSummary,
)
from app.models.user import User
from app.models.wallet import WalletTransaction, TXN_CHARGE
from app.services import feature_billing as fb


router = APIRouter()


# ── Global registry management ────────────────────────────────────────


@router.get("/features", response_model=List[FeatureRegistryRead])
def admin_list_features(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """List all features in the registry (admin view)."""
    stmt = select(FeatureRegistry).order_by(
        FeatureRegistry.category, FeatureRegistry.slug,
    )
    if not include_inactive:
        stmt = stmt.where(FeatureRegistry.is_active == True)  # noqa: E712
    rows = session.exec(stmt).all()
    return [FeatureRegistryRead.model_validate(r.model_dump()) for r in rows]


@router.get("/features/{slug}", response_model=FeatureRegistryRead)
def admin_get_feature(
    slug: str,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    reg = session.get(FeatureRegistry, slug)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Feature '{slug}' not found")
    return FeatureRegistryRead.model_validate(reg.model_dump())


@router.patch("/features/{slug}", response_model=FeatureRegistryRead)
def admin_update_feature(
    slug: str,
    body: FeatureRegistryUpdate,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Update default_price / enabled_by_default / is_active / description.

    Doesn't allow renaming slug, billing_unit, category (creates inconsistency
    with usage history).
    """
    reg = session.get(FeatureRegistry, slug)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Feature '{slug}' not found")

    if body.default_price_cents is not None:
        reg.default_price_cents = body.default_price_cents
    if body.enabled_by_default is not None:
        reg.enabled_by_default = body.enabled_by_default
    if body.is_active is not None:
        reg.is_active = body.is_active
    if body.description is not None:
        reg.description = body.description
    reg.updated_at = datetime.utcnow()

    session.add(reg)
    session.commit()
    session.refresh(reg)
    return FeatureRegistryRead.model_validate(reg.model_dump())


# ── Per-customer feature management ───────────────────────────────────


@router.get("/customers/{cid}/features", response_model=List[CustomerFeatureRead])
def admin_list_customer_features(
    cid: int,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """List all features with resolved enabled/price for a customer."""
    if not session.get(Customer, cid):
        raise HTTPException(status_code=404, detail="Customer not found")
    rows = fb.list_customer_features(session, cid)
    return [CustomerFeatureRead.model_validate(r) for r in rows]


@router.put("/customers/{cid}/features/{slug}", response_model=CustomerFeatureRead)
def admin_set_customer_feature(
    cid: int,
    slug: str,
    body: CustomerFeatureUpdate,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Open / close / override price for a specific feature on a specific customer."""
    if not session.get(Customer, cid):
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        fb.upsert_customer_feature(
            session, cid, slug,
            enabled=body.enabled,
            custom_price_cents=body.custom_price_cents,
            notes=body.notes,
            granted_by_user_id=current_user.id,
        )
    except fb.UnknownFeatureError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return resolved view (consistent with list endpoint)
    resolved = fb.list_customer_features(session, cid)
    for r in resolved:
        if r["feature_slug"] == slug:
            return CustomerFeatureRead.model_validate(r)
    raise HTTPException(status_code=500, detail="Resolved feature not found after upsert")


@router.delete("/customers/{cid}/features/{slug}", status_code=204)
def admin_remove_customer_feature(
    cid: int,
    slug: str,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Remove customer's override row. Falls back to registry default afterwards."""
    if not session.get(Customer, cid):
        raise HTTPException(status_code=404, detail="Customer not found")
    fb.delete_customer_feature(session, cid, slug)
    return None


# ── Usage aggregation ─────────────────────────────────────────────────


@router.get("/customers/{cid}/usage", response_model=List[FeatureUsageSummary])
def admin_get_customer_usage(
    cid: int,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Aggregate wallet_transaction (type=charge) by feature_slug for last N days.

    Note: we derive feature_slug from idempotency_key prefix ('feat:<slug>:...').
    """
    if not session.get(Customer, cid):
        raise HTTPException(status_code=404, detail="Customer not found")

    since = datetime.utcnow() - timedelta(days=days)

    rows = session.exec(
        select(WalletTransaction).where(
            WalletTransaction.customer_id == cid,
            WalletTransaction.type == TXN_CHARGE,
            WalletTransaction.created_at >= since,
        ).order_by(WalletTransaction.created_at.desc())
    ).all()

    # Bucket by feature slug
    buckets: dict[str, dict] = {}
    for txn in rows:
        if not txn.idempotency_key.startswith("feat:"):
            continue
        # 'feat:<slug>:<rest>' → slug
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
        # 单价反推 units（最佳努力）
        reg = session.get(FeatureRegistry, slug)
        if reg:
            b["name_zh"] = reg.name_zh
            # Resolve current customer price (may differ from when charged)
            unit = fb.get_unit_price_cents(session, cid, slug)
            if unit > 0:
                b["units_consumed"] += abs(txn.amount_cents) // unit
        if b["last_charged_at"] is None or txn.created_at > b["last_charged_at"]:
            b["last_charged_at"] = txn.created_at

    return [FeatureUsageSummary.model_validate(b) for b in sorted(
        buckets.values(), key=lambda x: -x["total_charged_cents"]
    )]
