"""Customer.icp_profile_text 变更后, 应自动更新 icp_profile_embedding"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.customer_icp_service import (
    set_customer_icp_text_and_embed,
)


@pytest.mark.asyncio
async def test_set_icp_text_calls_embedding():
    """正常路径: 设新 ICP → 调 embed → 写回 embedding 字段"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text=None, icp_profile_embedding=None)
    fake_session.get.return_value = fake_customer
    fake_vec = [0.1] * 768
    with patch(
        "app.services.customer_icp_service.embed_text",
        new=AsyncMock(return_value=fake_vec),
    ):
        ok = await set_customer_icp_text_and_embed(
            session=fake_session, customer_id=1, new_text="我的理想客户"
        )
    assert ok is True
    assert fake_customer.icp_profile_text == "我的理想客户"
    assert fake_customer.icp_profile_embedding == fake_vec
    fake_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_set_icp_text_embedding_failure_keeps_text():
    """embedding 失败时, 仍写 text 但 embedding=None (Layer 2 会自动降级)"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1)
    fake_session.get.return_value = fake_customer
    with patch(
        "app.services.customer_icp_service.embed_text",
        new=AsyncMock(return_value=None),
    ):
        ok = await set_customer_icp_text_and_embed(
            session=fake_session, customer_id=1, new_text="x"
        )
    assert ok is True
    assert fake_customer.icp_profile_text == "x"
    assert fake_customer.icp_profile_embedding is None


@pytest.mark.asyncio
async def test_set_icp_text_empty_clears_both():
    """传空文本: 清空 text 和 embedding"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text="old", icp_profile_embedding=[1.0]*768)
    fake_session.get.return_value = fake_customer
    ok = await set_customer_icp_text_and_embed(
        session=fake_session, customer_id=1, new_text=""
    )
    assert ok is True
    assert fake_customer.icp_profile_text is None
    assert fake_customer.icp_profile_embedding is None


@pytest.mark.asyncio
async def test_set_icp_text_unknown_customer_returns_false():
    fake_session = MagicMock()
    fake_session.get.return_value = None
    ok = await set_customer_icp_text_and_embed(
        session=fake_session, customer_id=999, new_text="x"
    )
    assert ok is False


@pytest.mark.asyncio
async def test_set_icp_text_whitespace_only_clears():
    """全空白 → 视为清空"""
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text="old", icp_profile_embedding=[0.5]*768)
    fake_session.get.return_value = fake_customer
    ok = await set_customer_icp_text_and_embed(
        session=fake_session, customer_id=1, new_text="   \n  "
    )
    assert ok is True
    assert fake_customer.icp_profile_text is None
    assert fake_customer.icp_profile_embedding is None


@pytest.mark.asyncio
async def test_set_icp_text_trims_leading_trailing():
    fake_session = MagicMock()
    fake_customer = MagicMock(id=1, icp_profile_text=None)
    fake_session.get.return_value = fake_customer
    with patch(
        "app.services.customer_icp_service.embed_text",
        new=AsyncMock(return_value=[0.1]*768),
    ):
        await set_customer_icp_text_and_embed(
            session=fake_session, customer_id=1, new_text="  好客户  "
        )
    assert fake_customer.icp_profile_text == "好客户"
