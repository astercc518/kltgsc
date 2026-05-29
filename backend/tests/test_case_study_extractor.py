"""Case study extractor: 从客户主号聊天历史 LLM 抽取成交事件"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.case_study_extractor import extract_cases_for_customer


@pytest.mark.asyncio
async def test_extract_returns_list_of_cases():
    """LLM 返回数组 → service 解析成 case_studies 候选"""
    fake_session = MagicMock()
    fake_history = [
        MagicMock(text="客户 A 要买 100k USDT", sender_id=1),
        MagicMock(text="我们用场外结算 3 天到账", sender_id=2),
        MagicMock(text="已完成, 谢谢", sender_id=1),
    ]
    fake_llm_out = json.dumps([{
        "industry": "OTC", "deal_size": "100k USDT", "period": "3 days",
        "problem": "客户 A 需要 USDT 买入", "solution": "场外结算",
        "outcome": "3 天到账, 客户满意", "tags": ["OTC", "USDT"],
    }])

    with patch(
        "app.services.case_study_extractor._fetch_chat_history",
        return_value=fake_history,
    ), patch(
        "app.services.case_study_extractor._llm_extract",
        new=AsyncMock(return_value=fake_llm_out),
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert isinstance(cases, list)
    assert len(cases) == 1
    assert cases[0]["industry"] == "OTC"
    assert cases[0]["deal_size"] == "100k USDT"


@pytest.mark.asyncio
async def test_extract_no_history_returns_empty():
    fake_session = MagicMock()
    with patch(
        "app.services.case_study_extractor._fetch_chat_history", return_value=[],
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert cases == []


@pytest.mark.asyncio
async def test_extract_llm_failure_returns_empty():
    fake_session = MagicMock()
    fake_history = [MagicMock(text="x", sender_id=1)]
    with patch(
        "app.services.case_study_extractor._fetch_chat_history",
        return_value=fake_history,
    ), patch(
        "app.services.case_study_extractor._llm_extract",
        new=AsyncMock(return_value=None),
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert cases == []


@pytest.mark.asyncio
async def test_extract_malformed_json_returns_empty():
    fake_session = MagicMock()
    fake_history = [MagicMock(text="x", sender_id=1)]
    with patch(
        "app.services.case_study_extractor._fetch_chat_history",
        return_value=fake_history,
    ), patch(
        "app.services.case_study_extractor._llm_extract",
        new=AsyncMock(return_value="not a json"),
    ):
        cases = await extract_cases_for_customer(
            session=fake_session, customer_id=1, max_history=100,
        )
    assert cases == []
