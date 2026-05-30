"""
tme_search_adapter — supplementary group info fetcher by known username.

Used to verify existence and retrieve title/description/member-count for a
group whose username is already known (e.g. Phase 8 captcha join-verification).

NOTE: t.me does NOT support keyword search — it only serves single-username
lookup pages.  This module is NOT a TGStat keyword-search fallback; it cannot
replace TGStat for discovery.  Do not wire it as a keyword-search fallback.
"""
import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TME_BASE = "https://t.me"


async def fetch_group_info_by_username(username: str) -> Optional[dict]:
    """
    返回 {"title", "description", "members_count" (估)} 或 None.
    """
    if not username:
        return None
    url = f"{TME_BASE}/{username}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            html = r.text
    except Exception:
        logger.warning("t.me fetch failed for %s", username)
        return None

    # Parse Open Graph meta tags (simple regex)
    title = _extract_meta(html, "og:title")
    description = _extract_meta(html, "og:description")
    if not title:
        return None
    # members count is often in tgme_page_extra div, regex-match digits + "members"
    members = None
    m = re.search(r'(\d+(?:[ ,]\d+)*)\s+(?:subscribers|members)', html)
    if m:
        members = int(m.group(1).replace(",", "").replace(" ", ""))

    return {
        "title": title,
        "description": description,
        "members_count": members,
    }


def _extract_meta(html: str, prop: str) -> Optional[str]:
    pattern = rf'<meta property="{re.escape(prop)}" content="([^"]+)"'
    m = re.search(pattern, html)
    return m.group(1) if m else None
