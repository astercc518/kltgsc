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


from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_bge_reranker_uses_model_scores_for_ordering():
    """
    Mocks the fastembed model so we can verify our wrapper:
    - calls model.rerank(query, docs) once
    - sorts results by score desc
    - returns top_n (original_index, score) tuples
    """
    from app.services.reranker_service_bge import BGEReranker

    fake_model = MagicMock()
    # fastembed's rerank yields one score per doc, in input order
    fake_model.rerank.return_value = iter([0.2, 0.9, 0.5])

    reranker = BGEReranker(model_name="fake-model")
    # Inject the mock so we don't actually load anything
    reranker._model = fake_model

    result = await reranker.rerank(
        query="hello",
        docs=["a", "b", "c"],
        top_n=2,
    )

    # Highest score first: index 1 (0.9), then index 2 (0.5)
    assert result == [(1, 0.9), (2, 0.5)]
    fake_model.rerank.assert_called_once_with("hello", ["a", "b", "c"])


@pytest.mark.asyncio
async def test_bge_reranker_empty_docs_short_circuits():
    from app.services.reranker_service_bge import BGEReranker

    reranker = BGEReranker(model_name="fake-model")
    # No model load should happen at all
    result = await reranker.rerank("q", [], top_n=5)
    assert result == []
    assert reranker._model is None


@pytest.mark.asyncio
async def test_bge_reranker_top_n_clamped_to_doc_count():
    from app.services.reranker_service_bge import BGEReranker

    fake_model = MagicMock()
    fake_model.rerank.return_value = iter([0.1, 0.2])

    reranker = BGEReranker(model_name="fake-model")
    reranker._model = fake_model

    result = await reranker.rerank("q", ["a", "b"], top_n=10)
    assert len(result) == 2
    assert result[0][0] == 1  # higher score
