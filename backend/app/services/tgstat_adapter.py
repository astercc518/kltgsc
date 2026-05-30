"""
tgstat_adapter — 包装 TGStat API 搜群。

API doc: https://api.tgstat.com/
需要 TGSTAT_API_TOKEN 环境变量。
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TGSTAT_BASE_URL = "https://api.tgstat.com"
TGSTAT_TIMEOUT = 30.0


async def search_groups_by_keyword(
    *, keyword: str, country: Optional[str] = "cn", limit: int = 50,
) -> list[dict]:
    """
    搜索匹配关键词的群/频道。
    Returns: [{"username": str|None, "chat_id": int|None, "title": str,
               "participants_count": int, "category": str, "link": str}, ...]
    或失败时返回 []
    """
    token = os.getenv("TGSTAT_API_TOKEN")
    if not token:
        logger.warning("TGSTAT_API_TOKEN not set; group_discovery TGStat disabled")
        return []

    params = {
        "token": token,
        "q": keyword,
        "country": country,
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=TGSTAT_TIMEOUT) as client:
            r = await client.get(f"{TGSTAT_BASE_URL}/channels/search", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("TGStat search failed for keyword=%s", keyword)
        return []

    if data.get("status") != "ok":
        logger.warning("TGStat returned non-ok: %s", data)
        return []

    items = (data.get("response") or {}).get("items") or []
    result = []
    for item in items:
        username = item.get("username")
        chat_id = item.get("id")
        link = f"https://t.me/{username}" if username else f"https://t.me/c/{chat_id}"
        result.append({
            "username": username,
            "chat_id": chat_id,
            "title": item.get("title", ""),
            "participants_count": int(item.get("participants_count", 0)),
            "category": item.get("category", ""),
            "link": link,
        })
    return result
