"""
portal_join_failures — 客户查看失败加群队列.

Endpoints:
  GET  /portal/group-ai/join/failures        — list failed join_attempts
  POST /portal/group-ai/join/{id}/abandon    — mark attempt as 'abandoned'
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
from app.models.join_attempt import JoinAttempt, STATUS_ABANDONED, STATUS_FAILED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal/group-ai/join", tags=["portal-join-failures"])


@router.get("/failures")
async def list_join_failures(
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """Return join_attempts with status='failed' for this customer."""
    rows = list(
        session.exec(
            select(JoinAttempt)
            .where(
                JoinAttempt.customer_id == customer.id,
                JoinAttempt.status == STATUS_FAILED,
            )
            .order_by(JoinAttempt.updated_at.desc())  # type: ignore[union-attr]
            .limit(200)
        ).all()
    )
    return [
        {
            "id": r.id,
            "chat_link": r.chat_link,
            "status": r.status,
            "captcha_type": r.captcha_type,
            "last_error": r.last_error,
            "captcha_attempts": r.captcha_attempts,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@router.post("/{attempt_id}/abandon")
async def abandon_join_attempt(
    attempt_id: int,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """Mark a failed join_attempt as 'abandoned' so scanner stops retrying."""
    row = session.get(JoinAttempt, attempt_id)
    if row is None or row.customer_id != customer.id:
        raise HTTPException(404, "join_attempt not found")
    if row.status not in (STATUS_FAILED, "captcha"):
        raise HTTPException(409, f"cannot abandon attempt in state '{row.status}'")

    row.status = STATUS_ABANDONED
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    logger.info(
        "abandon_join_attempt: id=%s customer=%s", attempt_id, customer.id,
    )
    return {"ok": True}
