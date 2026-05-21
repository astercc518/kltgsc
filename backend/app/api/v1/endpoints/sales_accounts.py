"""
Sales-facing TG account ops (Phase G).

Mounted at /sales/accounts. The sales user only sees and manages the
Accounts admin has assigned to them (Account.assigned_to_sales_user_id +
_kind). Day-to-day ops: list with health, join group, leave group,
quick-scrape on a group.

Out of scope (admin-only): create account, delete, change role, change
session, reassign customer_id, set is_customer_main.
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps_sales import SalesContext, get_current_sales
from app.core.celery_app import celery_app
from app.core.db import get_session
from app.models.account import Account


router = APIRouter()


def _kind_for(sales: SalesContext) -> str:
    return "platform" if sales.kind == "platform" else "customer"


def _own_or_404(session: Session, sales: SalesContext, account_id: int) -> Account:
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="account not found")
    if acc.assigned_to_sales_user_id != sales.user_id \
            or acc.assigned_to_sales_kind != _kind_for(sales):
        raise HTTPException(status_code=404, detail="account not found")
    return acc


# ── Schemas ────────────────────────────────────────────────────────────


class SalesAccountRow(BaseModel):
    id: int
    phone_number: Optional[str]
    customized_username: Optional[str]
    customized_first_name: Optional[str]
    status: str
    role: Optional[str]
    customer_id: Optional[int]
    created_at: str
    daily_invite_count: Optional[int] = None   # last 24h
    lead_count: Optional[int] = None           # leads from this account


class JoinGroupRequest(BaseModel):
    group_link: str = Field(min_length=4, max_length=300)


class ScrapeRequest(BaseModel):
    group_link: str = Field(min_length=4, max_length=300)
    limit: int = Field(default=200, ge=1, le=5000)
    filter_active_only: bool = False
    filter_has_photo: bool = False
    filter_has_username: bool = False


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("", response_model=List[SalesAccountRow])
def list_my_accounts(
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from app.models.lead import Lead
    from app.models.invite_log import InviteLog

    accounts = session.exec(
        select(Account).where(
            Account.assigned_to_sales_user_id == sales.user_id,
            Account.assigned_to_sales_kind == _kind_for(sales),
        ).order_by(Account.id.asc())
    ).all()

    if not accounts:
        return []

    day_ago = datetime.utcnow() - timedelta(hours=24)
    acc_ids = [a.id for a in accounts]

    invite_rows = session.exec(
        select(InviteLog.account_id, func.count(InviteLog.id))
        .where(InviteLog.account_id.in_(acc_ids),
               InviteLog.created_at >= day_ago)
        .group_by(InviteLog.account_id)
    ).all()
    invites_today = {aid: cnt for aid, cnt in invite_rows}

    lead_rows = session.exec(
        select(Lead.account_id, func.count(Lead.id))
        .where(Lead.account_id.in_(acc_ids))
        .group_by(Lead.account_id)
    ).all()
    lead_counts = {aid: cnt for aid, cnt in lead_rows}

    return [
        SalesAccountRow(
            id=a.id,
            phone_number=a.phone_number,
            customized_username=a.customized_username,
            customized_first_name=a.customized_first_name,
            status=a.status,
            role=a.role,
            customer_id=a.customer_id,
            created_at=a.created_at.isoformat() if a.created_at else "",
            daily_invite_count=invites_today.get(a.id, 0),
            lead_count=lead_counts.get(a.id, 0),
        )
        for a in accounts
    ]


@router.post("/{account_id}/join-group")
async def join_group(
    account_id: int,
    payload: JoinGroupRequest,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    acc = _own_or_404(session, sales, account_id)
    if acc.status != "active":
        raise HTTPException(status_code=400, detail=f"account is {acc.status}")

    from app.services.telegram_client import join_group_with_client
    try:
        success, msg = await join_group_with_client(
            acc, payload.group_link.strip(), db_session=session
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success and "already" not in msg.lower():
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "account_id": account_id, "message": msg}


@router.post("/{account_id}/scrape")
def scrape_group(
    account_id: int,
    payload: ScrapeRequest,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    """Kick off a background scrape on a single group with this account.
    Returns the celery task id; results land in TargetUser via the existing
    scrape_members_batch_task pipeline."""
    acc = _own_or_404(session, sales, account_id)
    if acc.status != "active":
        raise HTTPException(status_code=400, detail=f"account is {acc.status}")

    filter_config: Optional[dict] = None
    if any([payload.filter_active_only, payload.filter_has_photo, payload.filter_has_username]):
        filter_config = {
            "active_only": payload.filter_active_only,
            "has_photo": payload.filter_has_photo,
            "has_username": payload.filter_has_username,
        }

    from app.models.scraping_task import ScrapingTask
    task_row = ScrapingTask(
        task_type="sales_quick_scrape",
        status="running",
        account_ids_json=json.dumps([acc.id]),
        group_links_json=json.dumps([payload.group_link.strip()]),
    )
    session.add(task_row)
    session.commit()
    session.refresh(task_row)

    celery_task = celery_app.send_task(
        "app.tasks.scraping_tasks.scrape_members_batch_task",
        args=[[acc.id], [payload.group_link.strip()], payload.limit, task_row.id, filter_config],
    )
    task_row.celery_task_id = celery_task.id
    session.add(task_row)
    session.commit()

    return {
        "ok": True,
        "task_id": task_row.id,
        "celery_task_id": celery_task.id,
        "account_id": account_id,
        "group_link": payload.group_link,
    }


@router.get("/{account_id}/scrape-tasks")
def list_scrape_tasks(
    account_id: int,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
) -> Any:
    """Recent scrape tasks initiated for this account, regardless of who
    started them (admin or this sales)."""
    _own_or_404(session, sales, account_id)
    from app.models.scraping_task import ScrapingTask
    rows = session.exec(
        select(ScrapingTask)
        .where(ScrapingTask.account_ids_json.like(f"%{account_id}%"))
        .order_by(ScrapingTask.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "task_type": r.task_type,
            "status": r.status,
            "success_count": r.success_count,
            "fail_count": r.fail_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in rows
    ]
