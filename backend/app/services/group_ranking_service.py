"""
group_ranking_service — 候选群综合评分 0-100。
高分群优先推荐给客户审批。
"""
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select

from app.models.keyword_monitor import KeywordMonitor

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Normalize a group identifier: strip whitespace, leading @, lowercase."""
    return s.strip().lstrip("@").lower()


def compute_score(
    *,
    members_count: Optional[int],
    daily_messages: Optional[int],
    category: Optional[str],
    customer_icp_keywords: list[str],
    is_already_monitored: bool,
    discovered_at: Optional[datetime] = None,
) -> float:
    """0-100 综合分数."""
    score = 0.0

    # 成员数 (max 30)
    if members_count and members_count > 0:
        score += min(30.0, (math.log10(members_count) / 5.0) * 30.0)

    # 日活 (max 30)
    if daily_messages and daily_messages > 0:
        score += min(30.0, (daily_messages / 100.0) * 3.0)

    # 类别匹配 (max 20)
    if category and customer_icp_keywords:
        category_lower = category.lower()
        match_count = sum(1 for kw in customer_icp_keywords if kw.lower() in category_lower)
        if customer_icp_keywords:
            score += min(20.0, (match_count / len(customer_icp_keywords)) * 20.0)

    # 新鲜度 (max 10)
    if discovered_at:
        now = datetime.now(timezone.utc)
        if (now - discovered_at).days < 30:
            score += 10.0

    # 已监听惩罚
    if is_already_monitored:
        score -= 30.0

    return max(0.0, min(100.0, score))


def build_monitored_set(*, session, customer_id: int) -> set:
    """
    F5: Build a normalized set of all target group identifiers already being
    monitored by this customer.  Call once per customer and pass the result to
    is_chat_already_monitored to avoid an extra DB query per candidate.
    """
    rows = session.exec(
        select(KeywordMonitor).where(KeywordMonitor.customer_id == customer_id)
    ).all()
    monitored: set = set()
    for m in rows:
        for t in (m.target_groups or "").split(","):
            t_norm = _norm(t)
            if t_norm:
                monitored.add(t_norm)
    return monitored


def is_chat_already_monitored(
    *, monitored_set: set, chat_username: Optional[str], chat_id: Optional[int],
) -> bool:
    """
    F4: Check whether a group is already in keyword_monitor.target_groups using
    normalized exact-match (strips leading @, lowercased) to avoid substring
    false-positives (e.g. 'usdt_otc' substring-matching '@usdt_otc_china').

    Accept a pre-built monitored_set from build_monitored_set() instead of
    hitting the DB on every candidate (F5 — hoist query out of per-keyword loop).
    """
    if not chat_username and not chat_id:
        return False
    # Build candidate needles in the same normalized form
    needles: set = set()
    if chat_username:
        needles.add(_norm(chat_username))
    if chat_id:
        needles.add(str(chat_id).strip())
    return bool(needles & monitored_set)
