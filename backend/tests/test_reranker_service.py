"""Reranker service interface + factory behavior (no real model loaded)."""
import pytest

from app.services.reranker_service import (
    RerankerService,
    NoopReranker,
    get_reranker,
)


@pytest.mark.asyncio
async def test_noop_reranker_returns_input_order_unchanged():
    reranker = NoopReranker()
    docs = ["doc a", "doc b", "doc c"]
    ranked = await reranker.rerank("query", docs, top_n=2)
    # Result is List[Tuple[index, score]]; NoopReranker preserves order
    assert ranked == [(0, 0.0), (1, 0.0)]


@pytest.mark.asyncio
async def test_noop_reranker_empty_docs():
    reranker = NoopReranker()
    assert await reranker.rerank("q", [], top_n=5) == []


def test_get_reranker_returns_noop_when_disabled(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.RERANK_ENABLED", False)
    # Reset singleton so the monkeypatch takes effect
    import app.services.reranker_service as rs
    rs._reranker_singleton = None
    reranker = get_reranker()
    assert isinstance(reranker, NoopReranker)


def test_reranker_service_is_abstract():
    with pytest.raises(TypeError):
        RerankerService()  # abstract → cannot instantiate
