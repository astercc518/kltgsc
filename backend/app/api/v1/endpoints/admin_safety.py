"""Admin endpoints for the LLM safety stack.

GET /admin/safety/stats — rolling 24h/7d aggregate of block/route decisions
GET /admin/safety/recent-blocks — last N L0/L1 hits for spot-check
GET /admin/safety/by-source — breakdown per source (qa_extract, director_reactive, ...)

All endpoints derive layer + routing attribution from the `source` field's
suffix (e.g. `chat_reply:routed_deepseek`). When Task 4.1.5 lands the
moderation_score / block_layer / routed_provider columns will provide a
cleaner signal; for now suffix matching is good enough.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func

from app.api.deps import get_current_admin
from app.core.db import get_session
from app.models.llm_usage import LLMUsage
from app.models.user import User

router = APIRouter()


@router.get("/stats")
def safety_stats(
    hours: int = Query(24, ge=1, le=720),
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Aggregate counts: total, L0-blocked, L1-blocked, routed-deepseek, routed-vertex."""
    since = datetime.utcnow() - timedelta(hours=hours)

    def _count(suffix: str) -> int:
        return session.exec(
            select(func.count(LLMUsage.id))
            .where(LLMUsage.ts > since)
            .where(LLMUsage.source.like(f"%{suffix}"))
        ).one()

    return {
        "since": since.isoformat(),
        "hours": hours,
        "total_calls": session.exec(
            select(func.count(LLMUsage.id)).where(LLMUsage.ts > since)
        ).one(),
        "blocked_L0": _count(":blocked_L0"),
        "blocked_L1": _count(":blocked_L1"),
        "routed_refuse": _count(":routed_refuse"),
        "routed_deepseek": _count(":routed_deepseek"),
        "routed_vertex": _count(":routed_vertex"),
    }


@router.get("/recent-blocks")
def recent_blocks(
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(LLMUsage)
        .where(
            (LLMUsage.source.like("%:blocked_L0")) |
            (LLMUsage.source.like("%:blocked_L1"))
        )
        .order_by(LLMUsage.ts.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id, "ts": r.ts.isoformat(),
            "source": r.source, "provider": r.provider,
            "account_id": r.account_id, "chat_id": r.chat_id,
        }
        for r in rows
    ]


@router.get("/by-source")
def stats_by_source(
    hours: int = Query(24, ge=1, le=720),
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = session.exec(
        select(LLMUsage.source, func.count(LLMUsage.id))
        .where(LLMUsage.ts > since)
        .group_by(LLMUsage.source)
        .order_by(func.count(LLMUsage.id).desc())
    ).all()
    return [{"source": s, "count": c} for s, c in rows]
