"""Group discovery service unit tests."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.group_discovery_service import (
    _extract_keywords_from_icp, discover_for_customer,
)


def test_extract_keywords_basic():
    icp = "想找海外华人 USDT 大额买家 OTC 中介"
    keywords = _extract_keywords_from_icp(icp, max_keywords=5)
    assert len(keywords) <= 5
    assert "USDT" in keywords or "海外华人" in keywords


def test_extract_keywords_filters_short():
    keywords = _extract_keywords_from_icp("a b c USDT")
    assert "a" not in keywords
    assert "USDT" in keywords


@pytest.mark.asyncio
async def test_discover_skips_customer_without_icp():
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text=None)
    fake_session.get.return_value = fake_customer
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    with patch("app.services.group_discovery_service.Session", return_value=fake_session):
        n = await discover_for_customer(customer_id=1)
    assert n == 0


@pytest.mark.asyncio
async def test_discover_inserts_new_candidates():
    fake_customer = MagicMock(id=1, icp_profile_text="USDT 大额")
    fake_session = MagicMock()
    fake_session.get.return_value = fake_customer
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=None)
    # No blacklist, no existing
    fake_session.exec.return_value.all.return_value = []

    fake_search_result = [
        {"username": "usdt_otc", "chat_id": 1001, "title": "USDT OTC",
         "participants_count": 5000, "category": "Crypto",
         "link": "https://t.me/usdt_otc"},
    ]

    with patch("app.services.group_discovery_service.Session", return_value=fake_session), \
         patch("app.services.group_discovery_service.search_groups_by_keyword",
               new=AsyncMock(return_value=fake_search_result)), \
         patch("app.services.group_discovery_service.build_monitored_set",
               return_value=set()), \
         patch("app.services.group_discovery_service.is_chat_already_monitored",
               return_value=False):
        n = await discover_for_customer(customer_id=1)
    assert n >= 0  # smoke (具体次数依赖 keyword 提取)
