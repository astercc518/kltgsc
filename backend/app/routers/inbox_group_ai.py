"""
Inbox Group AI API — 销售视角的"群内 AI 互动" + 副驾驶建议。

endpoints:
  GET  /inbox/group-ai/customers/{customer_id}/recent
  POST /inbox/group-ai/suggested/{pr_id}/approve
  PUT  /inbox/group-ai/suggested/{pr_id}
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import get_session, engine
from app.models.pending_reply import PendingReply, PendingReplyStatus
from app.api.deps import get_current_admin
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inbox/group-ai", tags=["inbox-group-ai"])

INBOX_LOOKBACK_HOURS = 72


def _fetch_inbox_rows(*, session, customer_id: int) -> list[PendingReply]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=INBOX_LOOKBACK_HOURS)
    stmt = (
        select(PendingReply).where(
            PendingReply.customer_id == customer_id,
            PendingReply.status.in_([
                PendingReplyStatus.SENT.value,
                PendingReplyStatus.SUGGESTED.value,
            ]),
            PendingReply.created_at >= cutoff,
        ).order_by(PendingReply.created_at.desc()).limit(100)
    )
    return list(session.exec(stmt).all())


@router.get("/customers/{customer_id}/recent")
def list_recent(
    customer_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    rows = _fetch_inbox_rows(session=session, customer_id=customer_id)
    return [
        {
            "id": r.id, "status": r.status, "reply_text": r.reply_text,
            "chat_id": r.chat_id, "source_user_id": r.source_user_id,
            "source_text": r.source_text,
            "sent_at": r.sent_at, "created_at": r.created_at,
            "solution_topic": r.layer3_solution_topic,
            "extracted_needs": r.layer3_needs,
        }
        for r in rows
    ]


class SuggestedEdit(BaseModel):
    reply_text: str


def _update_suggested_reply_text(*, pr_id: int, new_text: str) -> bool:
    with Session(engine) as session:
        obj = session.get(PendingReply, pr_id)
        if obj is None or obj.status != PendingReplyStatus.SUGGESTED.value:
            return False
        obj.reply_text = new_text
        session.add(obj)
        session.commit()
        return True


@router.put("/suggested/{pr_id}")
def edit_suggested(
    pr_id: int,
    body: SuggestedEdit,
    _admin: User = Depends(get_current_admin),
):
    ok = _update_suggested_reply_text(pr_id=pr_id, new_text=body.reply_text)
    if not ok:
        raise HTTPException(404, "suggested pending_reply not found")
    return {"ok": True}


async def approve_suggested_reply(*, pr_id: int) -> dict:
    """approve = 切到 composing → dispatch_send → status=sent + billing。"""
    # === Step 1: 在短 session 内做 status flip ===
    with Session(engine) as session:
        obj = session.get(PendingReply, pr_id)
        if obj is None:
            raise HTTPException(404, "not found")
        if obj.status != PendingReplyStatus.SUGGESTED.value:
            raise ValueError("not in suggested state")
        if not obj.reply_text:
            raise HTTPException(400, "no reply_text")
        # flip to composing so dispatch_send sees a valid state
        obj.status = PendingReplyStatus.COMPOSING.value
        session.add(obj)
        session.commit()
        session.refresh(obj)
        session.expunge(obj)  # detach so we can use it after session closes
    # === Step 2: Session 已关闭, 现在 dispatch (内含 30-120s sleep) ===
    # dispatch_send 内部自己开 session 做 mark_status SENT + billing
    from app.services.group_dispatcher import dispatch_send
    await dispatch_send(obj)
    return {"ok": True, "pending_reply_id": pr_id}


@router.post("/suggested/{pr_id}/approve")
async def approve_endpoint(
    pr_id: int,
    _admin: User = Depends(get_current_admin),
):
    try:
        return await approve_suggested_reply(pr_id=pr_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
