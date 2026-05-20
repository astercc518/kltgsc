"""
Admin Bulk Send tooling (W5).

Force-pause / force-cancel a customer's batch when something is stuck.
Lives on the admin side so support / on-call can recover without giving the
customer their wallet back.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.db import get_session
from datetime import datetime, timedelta

from sqlalchemy import func

from app.models.bulk_send import (
    BulkBatch, BulkBatchRead, BulkTarget,
    BATCH_DRAFT, BATCH_PENDING, BATCH_RUNNING, BATCH_PAUSED, BATCH_CANCELED,
    BATCH_COMPLETED, BATCH_FAILED,
    TARGET_FAILED, TARGET_SENT, TARGET_DELIVERED, TARGET_REPLIED,
)
from app.models.customer import Customer
from app.models.user import User
from app.models.wallet import CustomerWallet, WalletTransaction
from app.services.bulk_dispatch_service import (
    BulkDispatchError, pause_batch as _pause_batch,
)
from app.tasks.bulk_balance_watcher import LOW_BALANCE_THRESHOLD_CENTS


router = APIRouter()


def _require_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/batches", response_model=List[BulkBatchRead])
def list_all_batches(
    _: User = Depends(_require_superuser),
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """All customers' batches, newest first."""
    stmt = select(BulkBatch)
    if status:
        stmt = stmt.where(BulkBatch.status == status)
    if customer_id:
        stmt = stmt.where(BulkBatch.customer_id == customer_id)
    rows = session.exec(
        stmt.order_by(BulkBatch.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [BulkBatchRead.model_validate(r.model_dump()) for r in rows]


@router.post("/batches/{batch_id}/force-pause", response_model=BulkBatchRead)
def force_pause(
    batch_id: int,
    reason: str = Query("admin_force_pause", max_length=120),
    _: User = Depends(_require_superuser),
    session: Session = Depends(get_session),
) -> Any:
    """Hard-pause a running/pending batch regardless of customer state."""
    batch = session.get(BulkBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status not in (BATCH_PENDING, BATCH_RUNNING):
        raise HTTPException(
            status_code=400,
            detail=f"Batch is {batch.status}; only pending/running can be force-paused",
        )
    try:
        batch = _pause_batch(session, batch, reason=reason)
    except BulkDispatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BulkBatchRead.model_validate(batch.model_dump())


@router.get("/metrics")
def bulk_metrics(
    _: User = Depends(_require_superuser),
    session: Session = Depends(get_session),
    window_hours: int = Query(24, ge=1, le=720),
) -> Any:
    """Operational snapshot for bulk-send health.

    Returns: batch status counts, target outcomes in last N hours, top failing
    assigned accounts (proxy for ban-rate), wallet shortfall counts, and the
    LLM-free mock-mode flag.
    """
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    # Batch status distribution
    batch_status_rows = session.exec(
        select(BulkBatch.status, func.count(BulkBatch.id))
        .group_by(BulkBatch.status)
    ).all()
    batches_by_status = {row[0]: int(row[1]) for row in batch_status_rows}

    # Window: target outcomes
    sent = session.exec(
        select(func.count(BulkTarget.id))
        .where(BulkTarget.status.in_([TARGET_SENT, TARGET_DELIVERED, TARGET_REPLIED]))
        .where(BulkTarget.sent_at >= cutoff)
    ).one()
    failed = session.exec(
        select(func.count(BulkTarget.id))
        .where(BulkTarget.status == TARGET_FAILED)
        .where(BulkTarget.created_at >= cutoff)
    ).one()
    replied = session.exec(
        select(func.count(BulkTarget.id))
        .where(BulkTarget.status == TARGET_REPLIED)
        .where(BulkTarget.sent_at >= cutoff)
    ).one()

    total_attempts = (sent or 0) + (failed or 0)
    fail_rate = (failed / total_attempts) if total_attempts else 0.0
    reply_rate = (replied / sent) if sent else 0.0

    # Top failing assigned accounts (proxy for ban risk in real-send mode)
    top_failing_rows = session.exec(
        select(BulkTarget.assigned_account_id, func.count(BulkTarget.id))
        .where(BulkTarget.status == TARGET_FAILED)
        .where(BulkTarget.created_at >= cutoff)
        .where(BulkTarget.assigned_account_id.is_not(None))
        .group_by(BulkTarget.assigned_account_id)
        .order_by(func.count(BulkTarget.id).desc())
        .limit(5)
    ).all()
    top_failing_accounts = [
        {"account_id": row[0], "failures": int(row[1])} for row in top_failing_rows
    ]

    # Wallet metrics: low-balance customers + cumulative spend in window
    low_balance_count = session.exec(
        select(func.count(CustomerWallet.customer_id))
        .where(CustomerWallet.balance_cents < LOW_BALANCE_THRESHOLD_CENTS)
    ).one()
    notified_count = session.exec(
        select(func.count(CustomerWallet.customer_id))
        .where(CustomerWallet.low_balance_notified_at.is_not(None))
    ).one()
    spend_in_window_cents = session.exec(
        select(func.coalesce(func.sum(WalletTransaction.amount_cents), 0))
        .where(WalletTransaction.type == "charge")
        .where(WalletTransaction.created_at >= cutoff)
    ).one()
    # Charges are negative; flip sign for display
    spend_cents = -int(spend_in_window_cents or 0)

    # Mock-mode flag (env-driven; reflects what workers see)
    import os
    mock_mode = os.environ.get("BULK_SEND_MOCK", "0") == "1"

    return {
        "window_hours": window_hours,
        "generated_at": datetime.utcnow().isoformat(),
        "mock_mode": mock_mode,
        "batches_by_status": batches_by_status,
        "active_batches": (
            batches_by_status.get(BATCH_RUNNING, 0)
            + batches_by_status.get(BATCH_PENDING, 0)
        ),
        "window": {
            "sent": int(sent or 0),
            "failed": int(failed or 0),
            "replied": int(replied or 0),
            "fail_rate": round(fail_rate, 4),
            "reply_rate": round(reply_rate, 4),
            "spend_cents": spend_cents,
        },
        "top_failing_accounts": top_failing_accounts,
        "wallets": {
            "low_balance_count": int(low_balance_count or 0),
            "low_balance_notified_count": int(notified_count or 0),
            "threshold_cents": LOW_BALANCE_THRESHOLD_CENTS,
        },
    }


@router.post("/batches/{batch_id}/force-cancel", response_model=BulkBatchRead)
def force_cancel(
    batch_id: int,
    reason: str = Query("admin_force_cancel", max_length=120),
    _: User = Depends(_require_superuser),
    session: Session = Depends(get_session),
) -> Any:
    """Terminal-cancel any non-terminal batch. Already-charged wallet txns
    are preserved; pending targets stay as-is for audit but won't be sent."""
    batch = session.get(BulkBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status in (
        "completed", "failed", "canceled",
    ):
        raise HTTPException(status_code=400, detail=f"Batch already terminal: {batch.status}")

    from datetime import datetime
    batch.status = BATCH_CANCELED
    batch.paused_at = datetime.utcnow()
    batch.pause_reason = reason[:120]
    batch.completed_at = datetime.utcnow()
    batch.updated_at = datetime.utcnow()
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return BulkBatchRead.model_validate(batch.model_dump())
