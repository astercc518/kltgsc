"""
Customer-facing scrape endpoints (Epic A — TG 群控 / 群采集).

Routes (mounted at /customer/scrape):
    POST   /preview-cost           — estimate ceiling cost for N groups × limit
    POST   /batches                — create pending batch
    GET    /batches                — list customer's scrape batches
    GET    /batches/{id}           — batch detail
    POST   /batches/{id}/start     — dispatch Celery task
    DELETE /batches/{id}           — cancel a pending batch
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.scrape_batch import (
    ScrapeBatch,
    ScrapeBatchCreate,
    ScrapeBatchRead,
    ScrapeCostPreview,
)
from app.services import scrape_batch_service as svc
from app.services.feature_billing import (
    FeatureBillingError,
    FeatureNotEnabledError,
)
from app.services.wallet_service import InsufficientBalanceError


router = APIRouter()


class CostPreviewRequest(BaseModel):
    source_links: List[str]
    limit_per_group: int = Field(default=200, ge=1, le=10000)


@router.post("/preview-cost", response_model=ScrapeCostPreview)
def preview_cost(
    payload: CostPreviewRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    return svc.preview_cost(
        session, customer.id, payload.source_links, payload.limit_per_group,
    )


@router.post("/batches", response_model=ScrapeBatchRead, status_code=201)
def create_batch(
    payload: ScrapeBatchCreate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    try:
        batch = svc.create_batch_draft(
            session, customer,
            name=payload.name,
            source_links=payload.source_links,
            account_ids=payload.account_ids,
            limit_per_group=payload.limit_per_group,
            filter_active_only=payload.filter_active_only,
            filter_has_photo=payload.filter_has_photo,
            filter_has_username=payload.filter_has_username,
        )
    except svc.ScrapeBatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScrapeBatchRead.from_orm_with_json(batch)


@router.get("/batches", response_model=List[ScrapeBatchRead])
def list_batches(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    stmt = select(ScrapeBatch).where(ScrapeBatch.customer_id == customer.id)
    if status:
        stmt = stmt.where(ScrapeBatch.status == status)
    rows = session.exec(
        stmt.order_by(ScrapeBatch.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [ScrapeBatchRead.from_orm_with_json(b) for b in rows]


@router.get("/batches/{batch_id}", response_model=ScrapeBatchRead)
def get_batch(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    batch = session.get(ScrapeBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="batch not found")
    return ScrapeBatchRead.from_orm_with_json(batch)


@router.post("/batches/{batch_id}/start", response_model=ScrapeBatchRead)
def start_batch(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    try:
        batch = svc.start_batch(session, customer, batch_id)
    except svc.ScrapeBatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FeatureNotEnabledError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except FeatureBillingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScrapeBatchRead.from_orm_with_json(batch)


@router.delete("/batches/{batch_id}", response_model=ScrapeBatchRead)
def cancel_batch(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    try:
        batch = svc.cancel_batch(session, customer, batch_id)
    except svc.ScrapeBatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ScrapeBatchRead.from_orm_with_json(batch)
