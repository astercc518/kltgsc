"""
group_discovery_service — 主编排。

流程:
  for each customer with ICP set:
    extract keywords from icp_profile_text (LLM extract or simple tokenize)
    for each keyword:
      results = await tgstat_adapter.search_groups_by_keyword(keyword)
      for each result:
        if in discovery_blacklist: skip
        if in discovered_group with same chat_link: skip (already pending/decided)
        compute_score()
        insert discovered_group with status='pending'
"""
import logging
import re
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.db import engine
from app.models.customer import Customer
from app.models.discovered_group import DiscoveredGroup
from app.models.discovery_blacklist import DiscoveryBlacklist
from app.services.tgstat_adapter import search_groups_by_keyword
from app.services.group_ranking_service import (
    compute_score, is_chat_already_monitored,
)

logger = logging.getLogger(__name__)


def _extract_keywords_from_icp(icp_text: str, max_keywords: int = 5) -> list[str]:
    """
    简化: 从 ICP 文本提取关键 token (按词频/长度).
    生产改进版可以调 LLM 提关键搜索词.
    """
    tokens = re.findall(r'[一-鿿]+|[A-Za-z]{3,}', icp_text)
    # 简单去重 + 长度过滤
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        if len(t) >= 2:
            result.append(t)
        if len(result) >= max_keywords:
            break
    return result


async def discover_for_customer(
    *, customer_id: int, max_per_keyword: int = 20,
) -> int:
    """
    为单个客户跑发现流程, 返回新插入的 candidate 数.
    """
    with Session(engine) as session:
        customer = session.get(Customer, customer_id)
        if customer is None or not customer.icp_profile_text:
            logger.info("discovery: customer %s has no ICP, skipping", customer_id)
            return 0

        keywords = _extract_keywords_from_icp(customer.icp_profile_text)
        logger.info("discovery: customer %s keywords=%s", customer_id, keywords)

        blacklist_rows = session.exec(
            select(DiscoveryBlacklist).where(
                DiscoveryBlacklist.customer_id == customer_id
            )
        ).all()
        blacklist = {row.chat_link for row in blacklist_rows}

        existing_rows = session.exec(
            select(DiscoveredGroup).where(
                DiscoveredGroup.customer_id == customer_id,
                DiscoveredGroup.chat_link.isnot(None),  # type: ignore[union-attr]
            )
        ).all()
        existing_links = {row.chat_link for row in existing_rows if row.chat_link}

        n_inserted = 0
        for keyword in keywords:
            results = await search_groups_by_keyword(
                keyword=keyword, limit=max_per_keyword,
            )
            for r in results:
                link = r.get("link", "")
                if not link or link in blacklist or link in existing_links:
                    continue

                already_monitored = is_chat_already_monitored(
                    session=session, customer_id=customer_id,
                    chat_username=r.get("username"), chat_id=r.get("chat_id"),
                )

                score = compute_score(
                    members_count=r.get("participants_count"),
                    daily_messages=None,  # TGStat search 不直接返回, 后续可补
                    category=r.get("category"),
                    customer_icp_keywords=keywords,
                    is_already_monitored=already_monitored,
                    discovered_at=datetime.now(timezone.utc),
                )

                row = DiscoveredGroup(
                    customer_id=customer_id,
                    chat_username=r.get("username"),
                    chat_link=link,
                    chat_id=r.get("chat_id"),
                    title=r.get("title"),
                    members_count=r.get("participants_count"),
                    category=r.get("category"),
                    source="tgstat",
                    source_query=keyword,
                    score=score,
                    status="pending",
                    metadata_json=r,
                    discovered_at=datetime.now(timezone.utc),
                )
                session.add(row)
                existing_links.add(link)
                n_inserted += 1

        session.commit()
        logger.info("discovery: customer %s inserted %d candidates", customer_id, n_inserted)
        return n_inserted


async def discover_for_all_active_customers() -> dict:
    """Weekly batch entry. Returns {customer_id: inserted_count} dict."""
    with Session(engine) as session:
        customers = session.exec(
            select(Customer).where(
                Customer.icp_profile_text.isnot(None)  # type: ignore[union-attr]
            )
        ).all()
        customer_ids = [c.id for c in customers]

    result: dict[int, int] = {}
    for cid in customer_ids:
        try:
            n = await discover_for_customer(customer_id=cid)
            result[cid] = n
        except Exception:
            logger.exception("discovery failed for customer %s", cid)
            result[cid] = 0
    return result
