"""
AI 费用预估 API — 基于本地 token 计费（pricing.py）。

端点：
  GET /ai/usage/summary?days=30
  GET /ai/usage/timeline?days=30&interval=day
  GET /ai/usage/top?dim=account|persona|chat&days=7&limit=10
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.account import Account
from app.models.ai_persona import AIPersona
from app.models.llm_usage import LLMUsage

logger = logging.getLogger(__name__)

router = APIRouter()


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=max(1, days))


@router.get("/summary")
def usage_summary(
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
):
    """
    Returns totals + breakdown by source and by model for the last N days.
    """
    cutoff = _since(days)

    totals = session.exec(
        select(
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.count(LLMUsage.id),
        ).where(LLMUsage.ts >= cutoff)
    ).first()

    today_cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_cost = session.exec(
        select(func.coalesce(func.sum(LLMUsage.cost_usd), 0.0))
        .where(LLMUsage.ts >= today_cutoff)
    ).first()

    all_time_cost = session.exec(
        select(func.coalesce(func.sum(LLMUsage.cost_usd), 0.0))
    ).first()

    by_source_rows = session.exec(
        select(
            LLMUsage.source,
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.count(LLMUsage.id),
        )
        .where(LLMUsage.ts >= cutoff)
        .group_by(LLMUsage.source)
        .order_by(func.sum(LLMUsage.cost_usd).desc())
    ).all()

    by_model_rows = session.exec(
        select(
            LLMUsage.model,
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.count(LLMUsage.id),
        )
        .where(LLMUsage.ts >= cutoff)
        .group_by(LLMUsage.model)
        .order_by(func.sum(LLMUsage.cost_usd).desc())
    ).all()

    return {
        "range_days": days,
        "total_cost_usd": float(totals[0] or 0),
        "total_input_tokens": int(totals[1] or 0),
        "total_output_tokens": int(totals[2] or 0),
        "total_calls": int(totals[3] or 0),
        "today_cost_usd": float(today_cost or 0),
        "all_time_cost_usd": float(all_time_cost or 0),
        "by_source": [
            {
                "source": r[0],
                "cost_usd": float(r[1] or 0),
                "input_tokens": int(r[2] or 0),
                "output_tokens": int(r[3] or 0),
                "calls": int(r[4] or 0),
            }
            for r in by_source_rows
        ],
        "by_model": [
            {
                "model": r[0],
                "cost_usd": float(r[1] or 0),
                "input_tokens": int(r[2] or 0),
                "output_tokens": int(r[3] or 0),
                "calls": int(r[4] or 0),
            }
            for r in by_model_rows
        ],
    }


@router.get("/timeline")
def usage_timeline(
    days: int = Query(30, ge=1, le=365),
    interval: str = Query("day", pattern="^(day|hour)$"),
    session: Session = Depends(get_session),
):
    """
    Time-series cost by day (or hour). Uses PG date_trunc.
    """
    cutoff = _since(days)
    bucket = func.date_trunc(interval, LLMUsage.ts).label("bucket")

    rows = session.exec(
        select(
            bucket,
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0),
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
        )
        .where(LLMUsage.ts >= cutoff)
        .group_by(bucket)
        .order_by(bucket)
    ).all()

    return {
        "range_days": days,
        "interval": interval,
        "points": [
            {
                "ts": r[0].isoformat() if r[0] else None,
                "cost_usd": float(r[1] or 0),
                "calls": int(r[2] or 0),
                "input_tokens": int(r[3] or 0),
                "output_tokens": int(r[4] or 0),
            }
            for r in rows
        ],
    }


@router.get("/top")
def usage_top(
    dim: str = Query("account", pattern="^(account|persona|chat)$"),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """
    Top N consumers grouped by account / persona / chat.
    """
    cutoff = _since(days)
    if dim == "account":
        col = LLMUsage.account_id
    elif dim == "persona":
        col = LLMUsage.persona_id
    else:
        col = LLMUsage.chat_id

    rows = session.exec(
        select(
            col,
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0),
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
        )
        .where(LLMUsage.ts >= cutoff)
        .where(col.is_not(None))
        .group_by(col)
        .order_by(func.sum(LLMUsage.cost_usd).desc())
        .limit(limit)
    ).all()

    # Resolve names for account / persona
    name_map = {}
    ids = [r[0] for r in rows if r[0] is not None]
    if dim == "account" and ids:
        accs = session.exec(select(Account).where(Account.id.in_(ids))).all()
        name_map = {
            a.id: (a.customized_username or a.phone_number or f"acc#{a.id}") for a in accs
        }
    elif dim == "persona" and ids:
        ps = session.exec(select(AIPersona).where(AIPersona.id.in_(ids))).all()
        name_map = {p.id: p.name for p in ps}

    return {
        "dim": dim,
        "range_days": days,
        "items": [
            {
                "id": r[0],
                "name": name_map.get(r[0]) if dim != "chat" else str(r[0]),
                "cost_usd": float(r[1] or 0),
                "calls": int(r[2] or 0),
                "input_tokens": int(r[3] or 0),
                "output_tokens": int(r[4] or 0),
            }
            for r in rows
        ],
    }


@router.get("/pricing")
def get_pricing():
    """暴露当前价格表给前端展示"""
    from app.services.pricing import PRICING_USD_PER_1M
    return {"pricing_per_1m_tokens_usd": PRICING_USD_PER_1M}
