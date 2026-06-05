"""Daily lead summary — Celery beat task.

每天 09:00 Asia/Shanghai (= 01:00 UTC) 跑一次，统计某 customer 最近 24h
新增的 Lead，按命中关键词 + 来源群分组，输出到 logger.INFO（beat 日志可查）。

不依赖任何外部通道（邮件/TG）—— 看 `docker compose logs beat | grep
daily_lead_summary` 就够。后续要发到 Saved Messages / Slack 再扩。
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.models.lead import Lead

logger = logging.getLogger(__name__)

_FROM_PATTERN = re.compile(r"^From '([^']+)':")


def _extract_keyword(tags_json: str | None) -> str | None:
    """Lead.tags_json 形如 '["monitor:TG群发"]'，抽 keyword 部分。"""
    if not tags_json:
        return None
    try:
        for tag in json.loads(tags_json):
            if isinstance(tag, str) and tag.startswith("monitor:"):
                return tag[len("monitor:"):]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extract_group(notes: str | None) -> str | None:
    """Lead.notes 形如 "From '群标题': 消息片段..."，抽群标题。"""
    if not notes:
        return None
    m = _FROM_PATTERN.match(notes)
    return m.group(1) if m else None


@shared_task(name="app.tasks.daily_lead_summary.daily_lead_summary")
def daily_lead_summary(customer_id: int = 1, window_hours: int = 24) -> dict:
    """Summarize new leads for `customer_id` in the last `window_hours`."""
    since = datetime.utcnow() - timedelta(hours=window_hours)
    with Session(engine) as s:
        leads = s.exec(
            select(Lead)
            .where(Lead.customer_id == customer_id)
            .where(Lead.created_at >= since)
            .order_by(Lead.created_at.desc())
        ).all()

    kw_counter: Counter[str] = Counter()
    group_counter: Counter[str] = Counter()
    for ld in leads:
        if (kw := _extract_keyword(ld.tags_json)):
            kw_counter[kw] += 1
        if (gp := _extract_group(ld.notes)):
            group_counter[gp] += 1

    top_recent = [
        {
            "id": ld.id,
            "username": ld.username,
            "first_name": ld.first_name,
            "keyword": _extract_keyword(ld.tags_json),
            "group": _extract_group(ld.notes),
            "created_at": ld.created_at.isoformat() if ld.created_at else None,
        }
        for ld in leads[:5]
    ]

    report = {
        "customer_id": customer_id,
        "window_hours": window_hours,
        "since_utc": since.isoformat(),
        "total_new_leads": len(leads),
        "by_keyword": dict(kw_counter.most_common()),
        "by_group": dict(group_counter.most_common(20)),
        "top_5_recent": top_recent,
    }

    logger.info(
        "daily_lead_summary customer=%d window=%dh total=%d by_keyword=%s by_group=%s top5=%s",
        customer_id,
        window_hours,
        len(leads),
        json.dumps(report["by_keyword"], ensure_ascii=False),
        json.dumps(report["by_group"], ensure_ascii=False),
        json.dumps(top_recent, ensure_ascii=False),
    )
    return report
