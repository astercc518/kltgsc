"""
portal_discovery — 客户审批候选群 endpoints.

- GET /portal/group-ai/discovery/candidates?status=pending - list candidates
- POST /portal/group-ai/discovery/{id}/approve - approve a candidate
- POST /portal/group-ai/discovery/{id}/reject - reject + add to blacklist
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.account import Account
from app.models.discovered_group import DiscoveredGroup
from app.models.discovery_blacklist import DiscoveryBlacklist

logger = logging.getLogger(__name__)

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
    session.commit()

    # Phase 8: queue a join attempt via the first available worker account.
    # No existing pick_worker_account_for_chat() found — use simple fallback.
    worker = session.exec(
        select(Account).where(
            Account.customer_id == customer.id,
            Account.role == "worker",
            Account.status == "active",
        ).limit(1)
    ).first()

    if worker:
        from app.services.join_orchestrator import queue_join
        attempt_id = queue_join(
            customer_id=customer.id,
            account_id=worker.id,
            chat_link=row.chat_link,
            discovered_group_id=row.id,
        )
        logger.info(
            "approve_candidate: queued join_attempt=%s for group=%s worker=%s",
            attempt_id, row.id, worker.id,
        )
    else:
        logger.warning(
            "approve_candidate: no active worker account for customer=%s; "
            "group=%s approved but join not queued",
            customer.id, row.id,
        )

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
    # F1: guard against double-reject / reject-after-approve
    if row.status != "pending":
        raise HTTPException(409, f"cannot reject in state {row.status}")

    row.status = "rejected"
    row.decided_at = datetime.now(timezone.utc)
    # F9: decided_by — Phase 8 TODO: return (customer, customer_user) from dep
    # get_current_customer currently returns Customer ORM only; no user.id available here.
    session.add(row)

    # F3: only blacklist when chat_link is non-null (avoids unique-constraint collision)
    if row.chat_link:
        bl = DiscoveryBlacklist(
            customer_id=customer.id,
            chat_link=row.chat_link,
            reason="customer_rejected",
        )
        session.add(bl)
    session.commit()
    return {"ok": True}
