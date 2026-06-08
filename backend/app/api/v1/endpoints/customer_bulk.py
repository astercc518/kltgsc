"""
Customer-facing Bulk Send endpoints (TG Bulk Send W2).

Routes (mounted at /customer/bulk):
    POST   /preview-cost           — estimate cost for N targets
    POST   /batches                — create draft batch (CSV + variants)
    GET    /batches                — list customer's batches
    GET    /batches/{id}           — batch detail + variants + targets preview
    DELETE /batches/{id}           — cancel a draft batch (no refund here in W2)

Start / pause / resume live in W3 together with the dispatcher.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from pydantic import BaseModel, Field

from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BulkBatchCreate, BulkBatchRead, BulkBatchDetail, BulkTargetRead, BulkTemplateVariantRead,
    BulkCostPreviewRequest,
    BATCH_DRAFT, BATCH_PENDING, BATCH_PAUSED,
)
from app.models.customer import Customer
from app.services.bulk_send_service import (
    BulkSendError,
    create_batch_draft,
    preview_cost_cents,
)
from app.services.bulk_dispatch_service import (
    BulkDispatchError,
    start_batch as _start_batch,
    pause_batch as _pause_batch,
    resume_batch as _resume_batch,
)


router = APIRouter()


@router.post("/preview-cost")
def preview_cost(
    payload: BulkCostPreviewRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Estimate cost (cents) for sending payload.target_count messages now."""
    try:
        return preview_cost_cents(session, customer.id, payload.target_count)
    except BulkSendError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches", response_model=BulkBatchDetail, status_code=201)
def create_batch(
    payload: BulkBatchCreate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Create a draft batch with targets parsed from CSV + optional variants.

    Returns the persisted batch with its variants and a 20-row target preview.
    Status is 'draft' — call /batches/{id}/start (W3) to actually send.
    """
    try:
        batch, summary = create_batch_draft(
            session, customer,
            name=payload.name,
            message_template=payload.message_template,
            csv_text=payload.csv_text,
            variants=payload.variants,
            min_delay_sec=payload.min_delay_sec,
            max_delay_sec=payload.max_delay_sec,
        )
    except BulkSendError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_batch_detail(session, batch, parse_summary=summary)


@router.get("/batches", response_model=List[BulkBatchRead])
def list_batches(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """List customer's batches, most recent first."""
    stmt = select(BulkBatch).where(BulkBatch.customer_id == customer.id)
    if status:
        stmt = stmt.where(BulkBatch.status == status)
    rows = session.exec(
        stmt.order_by(BulkBatch.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [BulkBatchRead.model_validate(r.model_dump()) for r in rows]


@router.get("/batches/{batch_id}", response_model=BulkBatchDetail)
def get_batch(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Batch detail: counters, variants, first 20 targets for QC."""
    batch = session.get(BulkBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    return _build_batch_detail(session, batch)


@router.delete("/batches/{batch_id}")
def cancel_batch(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Cancel a draft/pending batch. Running batches must use /pause then /cancel in W3."""
    batch = session.get(BulkBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status not in (BATCH_DRAFT, BATCH_PENDING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete batch in status={batch.status}; pause+cancel via W3 endpoints instead",
        )
    # Explicit child cleanup — DB-level CASCADE is unreliable here because
    # SQLModel.metadata.create_all may have built the FK without ondelete.
    session.exec(
        select(BulkTarget).where(BulkTarget.batch_id == batch.id)
    )
    for t in session.exec(select(BulkTarget).where(BulkTarget.batch_id == batch.id)).all():
        session.delete(t)
    for v in session.exec(select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == batch.id)).all():
        session.delete(v)
    session.delete(batch)
    session.commit()
    return {"ok": True}


# ── Lifecycle (W3): start / pause / resume ─────────────────────────────


@router.post("/batches/{batch_id}/start", response_model=BulkBatchDetail)
def start(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Move draft (or paused) → pending and arm the dispatcher.

    Validates: status, ≥5 variants, wallet has ≥1 unit price. On success a
    bulk_dispatcher_task is queued; the batch flips to `running` once the
    dispatcher picks it up.
    """
    batch = session.get(BulkBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    try:
        batch = _start_batch(session, batch)
    except BulkDispatchError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Queue dispatcher (deferred import to avoid Celery boot at request time)
    from app.tasks.bulk_send_tasks import bulk_dispatcher_task
    bulk_dispatcher_task.delay(batch.id)

    return _build_batch_detail(session, batch)


@router.post("/batches/{batch_id}/pause", response_model=BulkBatchDetail)
def pause(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Move running/pending → paused. Workers observe and exit on next iteration."""
    batch = session.get(BulkBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    try:
        batch = _pause_batch(session, batch, reason="user_paused")
    except BulkDispatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _build_batch_detail(session, batch)


@router.post("/batches/{batch_id}/resume", response_model=BulkBatchDetail)
def resume(
    batch_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Move paused → pending and re-arm the dispatcher."""
    batch = session.get(BulkBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    try:
        batch = _resume_batch(session, batch)
    except BulkDispatchError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.tasks.bulk_send_tasks import bulk_dispatcher_task
    bulk_dispatcher_task.delay(batch.id)

    return _build_batch_detail(session, batch)


# ── Variant CRUD (W5) ──────────────────────────────────────────────────


class VariantCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    weight: int = Field(default=1, ge=1, le=100)


class VariantUpdate(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    weight: Optional[int] = Field(default=None, ge=1, le=100)


_MUTABLE_VARIANT_STATUSES = {BATCH_DRAFT, BATCH_PAUSED}


def _load_owned_batch(session: Session, customer_id: int, batch_id: int) -> BulkBatch:
    batch = session.get(BulkBatch, batch_id)
    if not batch or batch.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


def _load_variant_in_batch(session: Session, batch: BulkBatch, variant_id: int) -> BulkTemplateVariant:
    v = session.get(BulkTemplateVariant, variant_id)
    if not v or v.batch_id != batch.id:
        raise HTTPException(status_code=404, detail="Variant not found")
    return v


@router.post("/batches/{batch_id}/variants", response_model=BulkTemplateVariantRead, status_code=201)
def add_variant(
    batch_id: int,
    payload: VariantCreate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Add a message variant to a batch. Only allowed while draft/paused."""
    batch = _load_owned_batch(session, customer.id, batch_id)
    if batch.status not in _MUTABLE_VARIANT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit variants while batch is {batch.status}; pause first",
        )
    v = BulkTemplateVariant(
        batch_id=batch.id,
        content=payload.content.strip(),
        weight=payload.weight,
    )
    session.add(v)
    session.commit()
    session.refresh(v)
    return BulkTemplateVariantRead.model_validate(v.model_dump())


@router.put("/variants/{variant_id}", response_model=BulkTemplateVariantRead)
def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Edit a variant's content or weight. Only allowed while draft/paused."""
    v = session.get(BulkTemplateVariant, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    batch = _load_owned_batch(session, customer.id, v.batch_id)
    if batch.status not in _MUTABLE_VARIANT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit variants while batch is {batch.status}; pause first",
        )
    if payload.content is not None:
        v.content = payload.content.strip()
    if payload.weight is not None:
        v.weight = payload.weight
    session.add(v)
    session.commit()
    session.refresh(v)
    return BulkTemplateVariantRead.model_validate(v.model_dump())


@router.delete("/variants/{variant_id}")
def delete_variant(
    variant_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Delete a variant. Only allowed while draft/paused.

    Note: bulk_target rows that already referenced this variant retain a
    dangling variant_id (FK is nullable in practice via on-delete behavior).
    Already-sent history is preserved through wallet_transaction.
    """
    v = session.get(BulkTemplateVariant, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    batch = _load_owned_batch(session, customer.id, v.batch_id)
    if batch.status not in _MUTABLE_VARIANT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit variants while batch is {batch.status}; pause first",
        )
    # Clear targets that pointed at this variant so we don't violate FK
    session.exec(
        select(BulkTarget).where(BulkTarget.variant_id == v.id)
    )
    for t in session.exec(select(BulkTarget).where(BulkTarget.variant_id == v.id)).all():
        t.variant_id = None
        session.add(t)
    session.delete(v)
    session.commit()
    return {"ok": True}


# ── helpers ────────────────────────────────────────────────────────────


def _build_batch_detail(
    session: Session,
    batch: BulkBatch,
    parse_summary: Optional[dict] = None,
) -> BulkBatchDetail:
    variants = session.exec(
        select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == batch.id)
    ).all()
    targets_preview = session.exec(
        select(BulkTarget)
        .where(BulkTarget.batch_id == batch.id)
        .order_by(BulkTarget.id)
        .limit(20)
    ).all()
    detail = BulkBatchDetail(
        **batch.model_dump(),
        variants=[BulkTemplateVariantRead.model_validate(v.model_dump()) for v in variants],
        targets_preview=[BulkTargetRead.model_validate(t.model_dump()) for t in targets_preview],
        parse_summary=parse_summary,
    )
    return detail
