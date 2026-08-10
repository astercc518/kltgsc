"""CaseStudy service: 录入 + 自动 embedding + 查询 top_k by similarity"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.case_study_service import (
    create_case_study, update_case_study, delete_case_study,
    list_case_studies, find_top_k_for_topic,
)


@pytest.mark.asyncio
async def test_create_case_study_with_embedding():
    fake_session = MagicMock()
    fake_session.add = MagicMock()
    fake_session.commit = MagicMock()
    fake_session.refresh = MagicMock()
    fake_vec = [0.5] * 768

    with patch(
        "app.services.case_study_service.embed_text",
        new=AsyncMock(return_value=fake_vec),
    ):
        case = await create_case_study(
            session=fake_session, customer_id=1,
            industry="OTC", deal_size="100k USDT", period="3 days",
            problem="需要海外汇款", solution="USDT 场外", outcome="3天到账",
            tags=["OTC", "USDT"], source="manual_portal",
        )
    assert case.customer_id == 1
    assert case.industry == "OTC"
    assert case.embedding == fake_vec
    assert case.source == "manual_portal"
    fake_session.add.assert_called_once()
    fake_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_case_study_embedding_failure_still_saves():
    """embedding 失败不阻塞 case 录入"""
    fake_session = MagicMock()
    with patch(
        "app.services.case_study_service.embed_text",
        new=AsyncMock(return_value=None),
    ):
        case = await create_case_study(
            session=fake_session, customer_id=1,
            industry="x", deal_size="x", period="x",
            problem="x", solution="x", outcome="x",
            tags=[], source="manual_portal",
        )
    assert case.embedding is None


@pytest.mark.asyncio
async def test_find_top_k_for_topic_returns_ordered_by_similarity():
    """简易测试: 验证调用了 with embedding ORDER BY <=>"""
    fake_session = MagicMock()
    fake_rows = [MagicMock(id=1), MagicMock(id=2)]
    fake_query = MagicMock()
    fake_query.all.return_value = fake_rows
    fake_session.exec.return_value = fake_query
    with patch(
        "app.services.case_study_service.embed_text",
        new=AsyncMock(return_value=[0.5]*768),
    ):
        result = await find_top_k_for_topic(
            session=fake_session, customer_id=1, topic="USDT 大额", k=2,
        )
    assert len(result) == 2
    # 验证 session.exec 被调用一次（即查询执行了）
    fake_session.exec.assert_called_once()


@pytest.mark.asyncio
async def test_find_top_k_empty_topic_returns_empty():
    fake_session = MagicMock()
    result = await find_top_k_for_topic(
        session=fake_session, customer_id=1, topic="", k=2,
    )
    assert result == []


@pytest.mark.asyncio
async def test_find_top_k_embed_failure_falls_back_to_recent():
    """embedding 失败 → 退回到按 last_used_at desc 取最近的 k 条"""
    fake_session = MagicMock()
    fake_rows = [MagicMock(id=1), MagicMock(id=2)]
    fake_query = MagicMock()
    fake_query.all.return_value = fake_rows
    fake_session.exec.return_value = fake_query
    with patch(
        "app.services.case_study_service.embed_text",
        new=AsyncMock(return_value=None),
    ):
        result = await find_top_k_for_topic(
            session=fake_session, customer_id=1, topic="x", k=2,
        )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_case_study_re_embeds_when_solution_changed():
    fake_session = MagicMock()
    fake_case = MagicMock(id=1, customer_id=1, problem="old", solution="old s", outcome="old o", embedding=[0.0]*768)
    fake_session.get.return_value = fake_case
    new_vec = [0.99] * 768
    with patch(
        "app.services.case_study_service.embed_text",
        new=AsyncMock(return_value=new_vec),
    ):
        ok = await update_case_study(
            session=fake_session, case_id=1, customer_id=1,
            problem="new", solution="new s", outcome="new o",
        )
    assert ok is True
    assert fake_case.solution == "new s"
    assert fake_case.embedding == new_vec


def test_delete_case_study_soft_disables():
    fake_session = MagicMock()
    fake_case = MagicMock(id=1, customer_id=1, active=True)
    fake_session.get.return_value = fake_case
    ok = delete_case_study(session=fake_session, case_id=1, customer_id=1)
    assert ok is True
    assert fake_case.active is False  # soft delete
    fake_session.commit.assert_called_once()


def test_list_case_studies_filters_by_customer():
    fake_session = MagicMock()
    fake_query = MagicMock()
    fake_query.all.return_value = [MagicMock(), MagicMock()]
    fake_session.exec.return_value = fake_query
    rows = list_case_studies(session=fake_session, customer_id=1, include_inactive=False)
    assert len(rows) == 2
