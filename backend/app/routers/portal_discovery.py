"""
portal_discovery — 客户审批候选群 endpoints.

- GET /portal/group-ai/discovery/candidates?status=pending - list candidates
- POST /portal/group-ai/discovery/{id}/approve - approve a candidate
- POST /portal/group-ai/discovery/{id}/reject - reject + add to blacklist
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_session
from app.api.deps_customer import get_current_customer
from app.models.discovered_group import DiscoveredGroup
from app.models.discovery_blacklist import DiscoveryBlacklist

router = APIRouter(prefix="/portal/group-ai/discovery", tags=["portal-discovery"])


@router.get("/candidates")
async def list_candidates(
    status: str = "pending",
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    stmt = (
        select(DiscoveredGroup)
        .where(
            DiscoveredGroup.customer_id == customer.id,
            DiscoveredGroup.status == status,
        )
        .order_by(
            DiscoveredGroup.score.desc().nullslast(),  # type: ignore[union-attr]
            DiscoveredGroup.discovered_at.desc(),  # type: ignore[union-attr]
        )
        .limit(100)
    )
    rows = list(session.exec(stmt).all())
    return [
        {
            "id": r.id,
            "chat_link": r.chat_link,
            "chat_username": r.chat_username,
            "title": r.title,
            "members_count": r.members_count,
            "category": r.category,
            "source": r.source,
            "source_query": r.source_query,
            "score": r.score,
            "status": r.status,
            "discovered_at": r.discovered_at,
        }
        for r in rows
    ]


@router.post("/{candidate_id}/approve")
async def approve_candidate(
    candidate_id: int,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    row = session.get(DiscoveredGroup, candidate_id)
    if row is None or row.customer_id != customer.id:
        raise HTTPException(404, "candidate not found")
    if row.status != "pending":
        raise HTTPException(409, f"cannot approve in state {row.status}")

    row.status = "approved"
    row.decided_at = datetime.now(timezone.utc)
    session.add(row)

    # TODO Phase 8: 触发 captcha 流程加入群; 现在仅更新状态
    session.commit()
    return {"ok": True}


@router.post("/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: int,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    row = session.get(DiscoveredGroup, candidate_id)
    if row is None or row.customer_id != customer.id:
        raise HTTPException(404, "candidate not found")

    row.status = "rejected"
    row.decided_at = datetime.now(timezone.utc)
    session.add(row)

    # Add to blacklist
    bl = DiscoveryBlacklist(
        customer_id=customer.id,
        chat_link=row.chat_link or "",
        reason="customer_rejected",
        created_at=datetime.now(timezone.utc),
    )
    session.add(bl)
    session.commit()
    return {"ok": True}
