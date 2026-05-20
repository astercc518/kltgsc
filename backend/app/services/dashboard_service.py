"""
Epic 6.0 — Admin operations dashboard aggregations.

Six read-only aggregates serving the admin BusinessOps page:

  • platform_overview     — top-line KPIs (customers / subs / MRR / accounts / leads)
  • customer_health       — per-customer activity + quota usage
  • lead_funnel           — new → contacted → replied → interested → converted
  • account_pool          — pool composition: free / allocated / main / collector / banned
  • llm_cost              — daily LLM spend (last N days), by provider/source
  • handover_stats        — Epic 5.2 escalations: notified / claimed / link sent

All queries are read-only; no caching yet (TODO Epic 6.1 if it gets hot).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text as sa_text
from sqlmodel import Session, func, select, and_

from app.models.account import Account
from app.models.customer import (
    Customer, PLAN_PRICE_USD, PLAN_STARTER, PLAN_GROWTH, PLAN_PRO,
    STATUS_ACTIVE, STATUS_PENDING, STATUS_SUSPENDED, STATUS_CANCELED,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.lead import Lead
from app.models.llm_usage import LLMUsage
from app.models.source_group import SourceGroup
from app.models.subscription import (
    Invoice, INV_PAID, INV_PENDING,
    Subscription, SUB_ACTIVE,
)


# ──────────────────────────────────────────────────────────────────────────
# 1) Platform overview
# ──────────────────────────────────────────────────────────────────────────

def platform_overview(session: Session) -> Dict[str, Any]:
    cust_by_status = dict(
        session.exec(
            select(Customer.status, func.count(Customer.id))
            .group_by(Customer.status)
        ).all()
    )
    cust_by_plan = dict(
        session.exec(
            select(Customer.plan, func.count(Customer.id))
            .where(Customer.plan.is_not(None))
            .group_by(Customer.plan)
        ).all()
    )

    active_subs = session.exec(
        select(func.count()).select_from(Subscription).where(Subscription.status == SUB_ACTIVE)
    ).one()

    # MRR = sum of USD plan price for each active subscription
    mrr_usd = 0.0
    for plan, count in cust_by_plan.items():
        # only count plans whose customer is active
        active_count = session.exec(
            select(func.count())
            .select_from(Customer)
            .where(Customer.plan == plan, Customer.status == STATUS_ACTIVE)
        ).one()
        mrr_usd += PLAN_PRICE_USD.get(plan, 0) * (active_count or 0)

    acc_total = session.exec(select(func.count()).select_from(Account)).one()
    acc_allocated = session.exec(
        select(func.count()).select_from(Account).where(Account.customer_id.is_not(None))
    ).one()
    acc_main = session.exec(
        select(func.count()).select_from(Account).where(Account.is_customer_main == True)
    ).one()
    acc_banned = session.exec(
        select(func.count()).select_from(Account).where(Account.status == "banned")
    ).one()

    leads_total = session.exec(select(func.count()).select_from(Lead)).one()
    leads_24h = session.exec(
        select(func.count())
        .select_from(Lead)
        .where(Lead.created_at >= datetime.utcnow() - timedelta(hours=24))
    ).one()

    kb_total = session.exec(select(func.count()).select_from(KnowledgeBase)).one()
    groups_total = session.exec(select(func.count()).select_from(SourceGroup)).one()

    # Pending invoices (admin should chase these)
    pending_invoices = session.exec(
        select(func.count()).select_from(Invoice).where(Invoice.status == INV_PENDING)
    ).one()

    return {
        "customers": {
            "total": sum(cust_by_status.values()),
            "by_status": cust_by_status,
            "by_plan": cust_by_plan,
            "active_subs": active_subs,
        },
        "mrr_usd": round(mrr_usd, 2),
        "accounts": {
            "total": acc_total,
            "allocated": acc_allocated,
            "free": acc_total - acc_allocated - acc_main,
            "main_accounts": acc_main,
            "banned": acc_banned,
        },
        "leads": {
            "total": leads_total,
            "last_24h": leads_24h,
        },
        "knowledge_base_total": kb_total,
        "source_groups_total": groups_total,
        "pending_invoices": pending_invoices,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────
# 2) Customer health
# ──────────────────────────────────────────────────────────────────────────

def customer_health(session: Session, limit: int = 100) -> List[Dict[str, Any]]:
    customers = session.exec(
        select(Customer).order_by(Customer.created_at.desc()).limit(limit)
    ).all()
    out = []
    for c in customers:
        acc_count = session.exec(
            select(func.count()).select_from(Account)
            .where(Account.customer_id == c.id, Account.is_customer_main == False)
        ).one()
        kb_count = session.exec(
            select(func.count()).select_from(KnowledgeBase)
            .where(KnowledgeBase.customer_id == c.id)
        ).one()
        lead_count = session.exec(
            select(func.count()).select_from(Lead)
            .where(Lead.customer_id == c.id)
        ).one()
        active_sub = session.exec(
            select(Subscription)
            .where(Subscription.customer_id == c.id, Subscription.status == SUB_ACTIVE)
        ).first()
        out.append({
            "id": c.id,
            "email": c.email,
            "industry": c.industry,
            "status": c.status,
            "plan": c.plan,
            "current_period_end": c.current_period_end.isoformat() if c.current_period_end else None,
            "main_account_bound": c.main_account_id is not None,
            "accounts": {
                "used": acc_count,
                "quota": c.account_quota,
                "pct": round(acc_count / c.account_quota * 100, 1) if c.account_quota else 0,
            },
            "kb_entries": kb_count,
            "leads": lead_count,
            "subscription_id": active_sub.id if active_sub else None,
            "created_at": c.created_at.isoformat(),
        })
    return out


# ──────────────────────────────────────────────────────────────────────────
# 3) Lead funnel (whole platform OR per-customer)
# ──────────────────────────────────────────────────────────────────────────

_FUNNEL_STAGES = ["new", "contacted", "replied", "interested", "converted", "closed"]


def lead_funnel(
    session: Session,
    customer_id: Optional[int] = None,
    days: int = 30,
) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(Lead.status, func.count(Lead.id))
        .where(Lead.created_at >= since)
        .group_by(Lead.status)
    )
    if customer_id is not None:
        stmt = stmt.where(Lead.customer_id == customer_id)
    counts_raw = dict(session.exec(stmt).all())

    stages = {s: int(counts_raw.get(s, 0)) for s in _FUNNEL_STAGES}
    total = sum(stages.values())

    # Conversion rate calc — replied / (new + contacted + replied) etc.
    # We use a simple linear interpretation: stage_n / sum(stage_0..n_minus_1)
    rates = {}
    for i, s in enumerate(_FUNNEL_STAGES[1:], start=1):
        prev_total = sum(stages[_FUNNEL_STAGES[j]] for j in range(i))
        rate = (stages[s] / prev_total * 100) if prev_total else 0.0
        rates[f"{_FUNNEL_STAGES[i-1]}_to_{s}"] = round(rate, 1)

    return {
        "window_days": days,
        "customer_id": customer_id,
        "total_leads": total,
        "stages": stages,
        "conversion_rates_pct": rates,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────
# 4) Account pool composition
# ──────────────────────────────────────────────────────────────────────────

def account_pool(session: Session) -> Dict[str, Any]:
    by_status = dict(session.exec(
        select(Account.status, func.count(Account.id))
        .group_by(Account.status)
    ).all())
    by_role = dict(session.exec(
        select(Account.role, func.count(Account.id))
        .group_by(Account.role)
    ).all())

    free_workers = session.exec(
        select(func.count()).select_from(Account)
        .where(
            Account.customer_id.is_(None),
            Account.is_customer_main == False,
            Account.role != "collector",
            Account.role != "main",
            Account.status.in_(["init", "active"]),
        )
    ).one()

    # Health-score histogram (buckets 0-20, 20-40, 40-60, 60-80, 80-100)
    health_buckets = {}
    for lo, hi in [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]:
        n = session.exec(
            select(func.count()).select_from(Account)
            .where(Account.health_score >= lo, Account.health_score < hi)
        ).one()
        health_buckets[f"{lo}-{hi-1 if hi == 101 else hi}"] = int(n)

    return {
        "by_status": by_status,
        "by_role": by_role,
        "free_for_allocation": int(free_workers),
        "health_score_buckets": health_buckets,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────
# 5) LLM cost (daily + by provider/source)
# ──────────────────────────────────────────────────────────────────────────

def llm_cost(session: Session, days: int = 14) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    # Daily totals — group by date(ts) is Postgres-specific
    daily_rows = session.execute(sa_text("""
        SELECT date_trunc('day', ts)::date::text AS day,
               SUM(cost_usd) AS cost,
               SUM(input_tokens) AS input_tok,
               SUM(output_tokens) AS output_tok,
               COUNT(*) AS calls
        FROM llm_usage
        WHERE ts >= :since
        GROUP BY day
        ORDER BY day
    """), {"since": since}).all()
    daily = [
        {
            "day": r[0], "cost_usd": float(r[1] or 0), "calls": int(r[4]),
            "input_tokens": int(r[2] or 0), "output_tokens": int(r[3] or 0),
        }
        for r in daily_rows
    ]

    by_source = dict(session.exec(
        select(LLMUsage.source, func.sum(LLMUsage.cost_usd))
        .where(LLMUsage.ts >= since)
        .group_by(LLMUsage.source)
    ).all())
    by_provider = dict(session.exec(
        select(LLMUsage.provider, func.sum(LLMUsage.cost_usd))
        .where(LLMUsage.ts >= since)
        .group_by(LLMUsage.provider)
    ).all())

    total_cost = sum(float(v or 0) for v in by_source.values())

    return {
        "window_days": days,
        "total_cost_usd": round(total_cost, 4),
        "daily": daily,
        "by_source": {k: round(float(v or 0), 4) for k, v in by_source.items()},
        "by_provider": {k: round(float(v or 0), 4) for k, v in by_provider.items()},
        "generated_at": datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────
# 6) Handover stats (Epic 5.2)
# ──────────────────────────────────────────────────────────────────────────

def handover_stats(session: Session, days: int = 30) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    notified = session.exec(
        select(func.count()).select_from(Lead)
        .where(Lead.main_account_notified_at >= since)
    ).one()
    handover_sent = session.exec(
        select(func.count()).select_from(Lead)
        .where(Lead.handover_link_sent_at >= since)
    ).one()
    claimed_in_time = session.exec(
        select(func.count()).select_from(Lead)
        .where(
            Lead.main_account_notified_at >= since,
            Lead.claimed_at.is_not(None),
            Lead.handover_link_sent_at.is_(None),
        )
    ).one()
    converted = session.exec(
        select(func.count()).select_from(Lead)
        .where(Lead.main_account_notified_at >= since, Lead.status == "converted")
    ).one()

    return {
        "window_days": days,
        "notified": notified,
        "claimed_in_time": claimed_in_time,
        "handover_link_sent": handover_sent,
        "converted": converted,
        "claim_rate_pct": round(claimed_in_time / notified * 100, 1) if notified else 0,
        "escalation_rate_pct": round(handover_sent / notified * 100, 1) if notified else 0,
        "conversion_rate_pct": round(converted / notified * 100, 1) if notified else 0,
        "generated_at": datetime.utcnow().isoformat(),
    }
