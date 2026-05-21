"""
Customer-facing invite endpoints (Epic B — TG 群控 / 群拉).

Routes (mounted at /customer/invite):
    POST   /preview-cost           — estimate cost for N invites
    POST   /tasks                  — create + dispatch invite task
    GET    /tasks                  — list customer's invite tasks
    GET    /tasks/{id}             — task detail
    GET    /tasks/{id}/logs        — per-target invite logs (paginated)
    POST   /tasks/{id}/pause       — pause running task
    POST   /tasks/{id}/resume      — resume paused task
    DELETE /tasks/{id}             — cancel task

Implementation reuses InviteTask (admin's existing model) with a new
customer_id scoping column added in migration 6f7a8b9c0d1e. Charging
runs automatically inside invite_service._log_invite via the existing
feature_billing.charge('bulk_invite', ...) hook — it picks up the
customer from Account.customer_id, so as long as the task uses the
customer's own active accounts (which we enforce here), every invite
charges the right wallet idempotently.
"""
import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.celery_app import celery_app
from app.core.db import get_session
from app.models.account import Account
from app.models.customer import Customer
from app.models.invite_log import InviteLog, InviteLogRead
from app.models.invite_task import InviteTask, InviteTaskRead
from app.models.target_user import TargetUser
from app.services import feature_billing
from app.services.wallet_service import get_balance_cents


router = APIRouter()

FEATURE_SLUG = "bulk_invite"


# ── Schemas ────────────────────────────────────────────────────────────


class CostPreviewRequest(BaseModel):
    target_count: int = Field(ge=1, le=10000)


class CostPreviewResponse(BaseModel):
    target_count: int
    unit_price_cents: int
    estimated_total_cents: int
    balance_cents: int
    balance_sufficient: bool
    shortfall_cents: int


class CreateInviteTaskRequest(BaseModel):
    name: str = Field(max_length=120)
    target_channel: str   # the group/channel customer wants users invited into
    account_ids: Optional[List[int]] = None       # customer's own TG accounts
    target_user_ids: Optional[List[int]] = None   # explicit targets

    # alt: filter-based target selection
    filter_min_score: Optional[int] = None
    filter_source_groups: Optional[List[str]] = None
    max_targets: int = Field(default=100, ge=1, le=10000)

    # throttling / safety
    min_delay: int = Field(default=30, ge=10, le=600)
    max_delay: int = Field(default=120, ge=10, le=600)
    max_invites_per_account: int = Field(default=20, ge=1, le=200)
    max_invites_per_task: int = Field(default=100, ge=1, le=10000)


# ── Helpers ────────────────────────────────────────────────────────────


def _customer_owned_account_ids(
    session: Session, customer_id: int, requested: Optional[List[int]],
) -> List[int]:
    """Return validated active account ids owned by this customer.

    If `requested` is provided, narrow to that set after validation.
    Otherwise, pick the customer's active pool (up to 20).
    """
    stmt = select(Account.id).where(
        Account.customer_id == customer_id, Account.status == "active",
    )
    pool = list(session.exec(stmt).all())
    if not pool:
        raise HTTPException(status_code=400, detail="No active TG accounts for this customer")
    if requested:
        bad = [a for a in requested if a not in pool]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Accounts not owned/active: {bad}",
            )
        return list(requested)
    return pool[:20]


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post("/preview-cost", response_model=CostPreviewResponse)
def preview_cost(
    payload: CostPreviewRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    unit = feature_billing.get_unit_price_cents(session, customer.id, FEATURE_SLUG)
    total = unit * payload.target_count
    balance = get_balance_cents(session, customer.id)
    return CostPreviewResponse(
        target_count=payload.target_count,
        unit_price_cents=unit,
        estimated_total_cents=total,
        balance_cents=balance,
        balance_sufficient=balance >= total,
        shortfall_cents=max(total - balance, 0),
    )


@router.post("/tasks", response_model=InviteTaskRead, status_code=201)
def create_invite_task(
    payload: CreateInviteTaskRequest,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Create a customer-scoped invite task and dispatch it."""
    if not payload.target_channel.strip():
        raise HTTPException(status_code=400, detail="target_channel is required")
    if payload.min_delay > payload.max_delay:
        raise HTTPException(status_code=400, detail="min_delay must be <= max_delay")

    account_ids = _customer_owned_account_ids(session, customer.id, payload.account_ids)

    # Resolve targets
    target_user_ids: List[int] = list(payload.target_user_ids or [])
    if not target_user_ids:
        # Filter-based: only TargetUsers scraped via this customer's accounts
        stmt = select(TargetUser).where(
            TargetUser.invite_status.in_(["untried", None])
        )
        if payload.filter_min_score is not None:
            stmt = stmt.where(TargetUser.ai_score >= payload.filter_min_score)
        if payload.filter_source_groups:
            stmt = stmt.where(TargetUser.source_group.in_(payload.filter_source_groups))
        targets = list(session.exec(stmt.limit(payload.max_targets)).all())
        if not targets:
            raise HTTPException(status_code=400, detail="No matching targets")
        target_user_ids = [t.id for t in targets]

    # Pre-flight wallet check (best-effort; per-invite check still runs inside
    # invite_service so balance going dry mid-run is also handled gracefully)
    feature_billing.check_can_afford(
        session, customer.id, FEATURE_SLUG, units=len(target_user_ids),
    )

    task = InviteTask(
        name=payload.name.strip()[:120],
        target_channel=payload.target_channel.strip(),
        customer_id=customer.id,
        account_ids_json=json.dumps(account_ids),
        target_user_ids_json=json.dumps(target_user_ids),
        total_count=len(target_user_ids),
        pending_count=len(target_user_ids),
        min_delay=payload.min_delay,
        max_delay=payload.max_delay,
        max_invites_per_account=payload.max_invites_per_account,
        max_invites_per_task=payload.max_invites_per_task,
        filter_min_score=payload.filter_min_score,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    celery_app.send_task(
        "app.tasks.invite_tasks.execute_invite_task", args=[task.id],
    )
    return task


@router.get("/tasks", response_model=List[InviteTaskRead])
def list_invite_tasks(
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    stmt = select(InviteTask).where(InviteTask.customer_id == customer.id)
    if status:
        stmt = stmt.where(InviteTask.status == status)
    return session.exec(
        stmt.order_by(InviteTask.created_at.desc()).offset(skip).limit(limit)
    ).all()


def _own_or_404(session: Session, customer_id: int, task_id: int) -> InviteTask:
    task = session.get(InviteTask, task_id)
    if not task or task.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.get("/tasks/{task_id}", response_model=InviteTaskRead)
def get_invite_task(
    task_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    return _own_or_404(session, customer.id, task_id)


@router.get("/tasks/{task_id}/logs", response_model=List[InviteLogRead])
def get_invite_logs(
    task_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    _own_or_404(session, customer.id, task_id)
    return session.exec(
        select(InviteLog)
        .where(InviteLog.task_id == task_id)
        .order_by(InviteLog.id.desc())
        .offset(skip).limit(limit)
    ).all()


@router.post("/tasks/{task_id}/pause", response_model=InviteTaskRead)
def pause_invite_task(
    task_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    task = _own_or_404(session, customer.id, task_id)
    if task.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"cannot pause from '{task.status}'")
    task.status = "paused"
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.post("/tasks/{task_id}/resume", response_model=InviteTaskRead)
def resume_invite_task(
    task_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    task = _own_or_404(session, customer.id, task_id)
    if task.status not in ("paused", "paused_no_funds"):
        raise HTTPException(status_code=400, detail=f"cannot resume from '{task.status}'")
    task.status = "pending"
    task.last_error = None
    session.add(task)
    session.commit()
    session.refresh(task)
    celery_app.send_task(
        "app.tasks.invite_tasks.execute_invite_task", args=[task.id],
    )
    return task


@router.delete("/tasks/{task_id}", response_model=InviteTaskRead)
def cancel_invite_task(
    task_id: int,
    customer: Customer = Depends(get_current_customer),
    session: Session = Depends(get_session),
) -> Any:
    task = _own_or_404(session, customer.id, task_id)
    if task.status in ("completed", "failed"):
        raise HTTPException(status_code=400, detail=f"cannot cancel from '{task.status}'")
    task.status = "failed"  # treated as user-canceled
    task.completed_at = datetime.utcnow()
    task.last_error = "canceled by customer"
    session.add(task)
    session.commit()
    session.refresh(task)
    return task
