"""
Sales-facing monitor rules (Phase G).

Mounted at /sales/monitors. Each rule's `created_by_sales_user_id +
_kind` is set to the caller automatically; the sales user only ever sees
and can only edit rules they authored. Global (admin) rules are not
listed here.

Listener scoping (G5) ensures these rules only fire on TG accounts the
same sales user is assigned to.
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps_sales import SalesContext, get_current_sales
from app.core.db import get_session
from app.models.keyword_monitor import (
    KeywordMonitor, KeywordMonitorCreate, KeywordMonitorRead, KeywordMonitorUpdate,
)


router = APIRouter()


def _kind_for(sales: SalesContext) -> str:
    return "platform" if sales.kind == "platform" else "customer"


def _own_or_404(session: Session, sales: SalesContext, monitor_id: int) -> KeywordMonitor:
    mon = session.get(KeywordMonitor, monitor_id)
    if not mon:
        raise HTTPException(status_code=404, detail="monitor not found")
    if mon.created_by_sales_user_id != sales.user_id \
            or mon.created_by_sales_kind != _kind_for(sales):
        raise HTTPException(status_code=404, detail="monitor not found")
    return mon


@router.get("", response_model=List[KeywordMonitorRead])
def list_my_monitors(
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
    is_active: Optional[bool] = Query(None),
) -> Any:
    stmt = select(KeywordMonitor).where(
        KeywordMonitor.created_by_sales_user_id == sales.user_id,
        KeywordMonitor.created_by_sales_kind == _kind_for(sales),
    )
    if is_active is not None:
        stmt = stmt.where(KeywordMonitor.is_active == is_active)
    rows = session.exec(stmt.order_by(KeywordMonitor.created_at.desc())).all()
    return rows


@router.post("", response_model=KeywordMonitorRead, status_code=201)
def create_monitor(
    payload: KeywordMonitorCreate,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    """Create a sales-owned monitor rule. Auto-tagged with the caller."""
    if not payload.keyword.strip():
        raise HTTPException(status_code=400, detail="keyword is required")
    if payload.marketing_mode == "active":
        # F4 / G safety: sales-owned rules never auto-DM. Spam risk + cost.
        raise HTTPException(
            status_code=400,
            detail="marketing_mode='active' not allowed for sales-owned monitors",
        )
    # Strip caller-supplied ownership fields — we always pin them to the
    # authenticated sales user regardless of what the client sends.
    data = payload.model_dump(exclude={"created_by_sales_user_id", "created_by_sales_kind"})
    data["created_by_sales_user_id"] = sales.user_id
    data["created_by_sales_kind"] = _kind_for(sales)
    mon = KeywordMonitor(**data)
    session.add(mon)
    session.commit()
    session.refresh(mon)
    return mon


@router.get("/{monitor_id}", response_model=KeywordMonitorRead)
def get_monitor(
    monitor_id: int,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    return _own_or_404(session, sales, monitor_id)


@router.put("/{monitor_id}", response_model=KeywordMonitorRead)
def update_monitor(
    monitor_id: int,
    payload: KeywordMonitorUpdate,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    mon = _own_or_404(session, sales, monitor_id)
    if payload.marketing_mode == "active":
        raise HTTPException(status_code=400,
            detail="marketing_mode='active' not allowed for sales-owned monitors")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(mon, k, v)
    session.add(mon)
    session.commit()
    session.refresh(mon)
    return mon


@router.delete("/{monitor_id}")
def delete_monitor(
    monitor_id: int,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
) -> Any:
    mon = _own_or_404(session, sales, monitor_id)
    session.delete(mon)
    session.commit()
    return {"ok": True, "id": monitor_id}


class RecentHitRow(BaseModel):
    id: int
    source_group_name: Optional[str]
    source_user_name: Optional[str]
    snippet: str
    detected_at: str


@router.get("/{monitor_id}/recent-hits", response_model=List[RecentHitRow])
def recent_hits(
    monitor_id: int,
    sales: SalesContext = Depends(get_current_sales),
    session: Session = Depends(get_session),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    _own_or_404(session, sales, monitor_id)
    from datetime import datetime, timedelta
    from app.models.keyword_monitor import KeywordHit
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = session.exec(
        select(KeywordHit)
        .where(KeywordHit.keyword_monitor_id == monitor_id,
               KeywordHit.detected_at >= cutoff)
        .order_by(KeywordHit.detected_at.desc())
        .limit(limit)
    ).all()
    return [
        RecentHitRow(
            id=h.id,
            source_group_name=h.source_group_name,
            source_user_name=h.source_user_name,
            snippet=(h.message_content or "")[:160],
            detected_at=h.detected_at.isoformat(),
        )
        for h in rows
    ]
