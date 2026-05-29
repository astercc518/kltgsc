"""embedding_service: 薄包装 industry_kb_service._embed_text, 统一调用入口"""
from unittest.mock import patch, MagicMock

from app.services.embedding_service import embed_text


def test_embed_text_returns_768d_vector():
    """成功路径: 返回 768 维 float list"""
    fake_vec = [0.1] * 768
    with patch(
        "app.services.embedding_service._embed_text_raw",
        return_value=fake_vec,
    ):
        result = embed_text(session=MagicMock(), text="test ICP")
    assert isinstance(result, list)
    assert len(result) == 768


def test_embed_text_none_on_empty():
    """空文本不调 embedding, 直接 None"""
    result = embed_text(session=MagicMock(), text="")
    assert result is None
    result2 = embed_text(session=MagicMock(), text=None)
    assert result2 is None


def test_embed_text_none_on_underlying_failure():
    """底层服务挂 → None (调用方 fail-soft)"""
    with patch(
        "app.services.embedding_service._embed_text_raw",
        return_value=None,
    ):
        result = embed_text(session=MagicMock(), text="x")
    assert result is None


def test_embed_text_none_on_underlying_exception():
    """底层抛异常 → None (不传播)"""
    with patch(
        "app.services.embedding_service._embed_text_raw",
        side_effect=Exception("LLM down"),
    ):
        result = embed_text(session=MagicMock(), text="x")
    assert result is None


def test_embed_text_strips_whitespace_only():
    """全空白 → None"""
    result = embed_text(session=MagicMock(), text="   \n\t  ")
    assert result is None
