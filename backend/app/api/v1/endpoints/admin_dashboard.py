"""
Epic 6.0 — Admin business-ops dashboard endpoints.

All endpoints require admin auth (get_current_admin) and return aggregated,
read-only data computed on the fly. No caching yet — switch to Redis-backed
caching if any of these hot up in prod.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_current_admin
from app.core.db import get_session
from app.models.user import User
from app.services import dashboard_service


router = APIRouter()


@router.get("/overview")
def overview(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Top-line KPIs: customers, subs, MRR, accounts, leads, KB."""
    return dashboard_service.platform_overview(session)


@router.get("/customers")
def customers(
    limit: int = Query(100, ge=1, le=500),
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Per-customer health: plan, quota usage, KB count, lead count."""
    return dashboard_service.customer_health(session, limit=limit)


@router.get("/lead-funnel")
def lead_funnel(
    customer_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Lead funnel: new → contacted → replied → interested → converted.

    Pass customer_id to drill into a single tenant; omit for platform-wide.
    """
    return dashboard_service.lead_funnel(session, customer_id=customer_id, days=days)


@router.get("/account-pool")
def account_pool(
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Account pool composition by status, role, and health score."""
    return dashboard_service.account_pool(session)


@router.get("/llm-usage")
def llm_usage(
    days: int = Query(14, ge=1, le=90),
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """LLM cost breakdown: daily series + by source/provider."""
    return dashboard_service.llm_cost(session, days=days)


@router.get("/handover-stats")
def handover_stats(
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """Epic 5.2 handover effectiveness: notify → claim vs escalate vs convert."""
    return dashboard_service.handover_stats(session, days=days)
