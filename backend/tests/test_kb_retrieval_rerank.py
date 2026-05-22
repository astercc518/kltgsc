"""
Verifies that _vector_search uses the reranker when RERANK_ENABLED is true
and falls back to cosine order otherwise. The pgvector SQL is mocked.
"""
import pytest
from unittest.mock import patch

from app.models.knowledge_base import KnowledgeBase
from app.services import reranker_service
from app.services.kb_retrieval import _vector_search


@pytest.fixture
def kb_rows(session):
    """Persist three KBs with deterministic ids/text we can reason about."""
    rows = [
        KnowledgeBase(id=1, name="k1", content="content one", qa_answer="answer one"),
        KnowledgeBase(id=2, name="k2", content="content two", qa_answer="answer two"),
        KnowledgeBase(id=3, name="k3", content="content three", qa_answer="answer three"),
    ]
    for kb in rows:
        session.add(kb)
    session.commit()
    return rows


@pytest.mark.asyncio
async def test_vector_search_skips_reranker_when_disabled(session, kb_rows, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.RERANK_ENABLED", False)
    reranker_service.reset_reranker_for_tests()

    fake_rows = [(1, 0.1), (2, 0.2), (3, 0.3)]
    with patch("app.services.kb_retrieval.sa_text"), \
         patch.object(session, "execute") as exec_mock:
        exec_mock.return_value.fetchall.return_value = fake_rows

        result = await _vector_search(
            session=session,
            query="hello",
            qvec=[0.0] * 768,
            top_k=2,
            chat_id_filter=None,
            topic_filter=None,
            source_type=None,
            category_filter=None,
            similarity_threshold=0.45,
            customer_id_filter=None,
        )

    # Reranker off → cosine order preserved (smallest distance first → id 1, 2)
    assert [kb.id for kb in result] == [1, 2]


@pytest.mark.asyncio
async def test_vector_search_uses_reranker_when_enabled(session, kb_rows, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.RERANK_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.RERANK_CANDIDATE_MULTIPLIER", 5)
    monkeypatch.setattr("app.core.config.settings.RERANK_TIMEOUT_MS", 800)

    # Stub reranker that returns docs in REVERSE input order
    class ReverseReranker(reranker_service.RerankerService):
        async def rerank(self, query, docs, top_n):
            n = len(docs)
            return [(n - 1 - i, float(n - i)) for i in range(min(top_n, n))]

    reranker_service.reset_reranker_for_tests()
    reranker_service._reranker_singleton = ReverseReranker()

    fake_rows = [(1, 0.1), (2, 0.2), (3, 0.3)]
    with patch("app.services.kb_retrieval.sa_text"), \
         patch.object(session, "execute") as exec_mock:
        exec_mock.return_value.fetchall.return_value = fake_rows

        result = await _vector_search(
            session=session,
            query="hello",
            qvec=[0.0] * 768,
            top_k=2,
            chat_id_filter=None,
            topic_filter=None,
            source_type=None,
            category_filter=None,
            similarity_threshold=0.45,
            customer_id_filter=None,
        )

    # ReverseReranker reverses order → expect [3, 2] as top-2
    assert [kb.id for kb in result] == [3, 2]


@pytest.mark.asyncio
async def test_vector_search_fetches_wider_candidate_set_when_rerank_enabled(
    session, kb_rows, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.RERANK_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.RERANK_CANDIDATE_MULTIPLIER", 5)
    monkeypatch.setattr("app.core.config.settings.RERANK_TIMEOUT_MS", 800)

    reranker_service.reset_reranker_for_tests()
    reranker_service._reranker_singleton = reranker_service.NoopReranker()

    with patch("app.services.kb_retrieval.sa_text"), \
         patch.object(session, "execute") as exec_mock:
        exec_mock.return_value.fetchall.return_value = [(1, 0.1)]

        await _vector_search(
            session=session,
            query="hello",
            qvec=[0.0] * 768,
            top_k=3,
            chat_id_filter=None,
            topic_filter=None,
            source_type=None,
            category_filter=None,
            similarity_threshold=0.45,
            customer_id_filter=None,
        )

    # session.execute(sql, params) — params is positional arg 1
    params = exec_mock.call_args[0][1]
    # top_k=3, multiplier=5 → 15. (When reranker disabled it would be top_k * 2 = 6.)
    assert params["top_k"] == 15


@pytest.mark.asyncio
async def test_vector_search_falls_back_to_cosine_on_reranker_exception(
    session, kb_rows, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.RERANK_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.RERANK_TIMEOUT_MS", 800)

    class BrokenReranker(reranker_service.RerankerService):
        async def rerank(self, query, docs, top_n):
            raise RuntimeError("boom")

    reranker_service.reset_reranker_for_tests()
    reranker_service._reranker_singleton = BrokenReranker()

    fake_rows = [(1, 0.1), (2, 0.2), (3, 0.3)]
    with patch("app.services.kb_retrieval.sa_text"), \
         patch.object(session, "execute") as exec_mock:
        exec_mock.return_value.fetchall.return_value = fake_rows

        result = await _vector_search(
            session=session,
            query="hello",
            qvec=[0.0] * 768,
            top_k=2,
            chat_id_filter=None,
            topic_filter=None,
            source_type=None,
            category_filter=None,
            similarity_threshold=0.45,
            customer_id_filter=None,
        )

    # Reranker raised → fall back to cosine order (top-2 of distance-sorted ids)
    assert [kb.id for kb in result] == [1, 2]


@pytest.mark.asyncio
async def test_vector_search_falls_back_to_cosine_on_reranker_timeout(
    session, kb_rows, monkeypatch
):
    """asyncio.TimeoutError carries no .message — exercise the path that
    motivated logging with exc_info=True."""
    import asyncio

    monkeypatch.setattr("app.core.config.settings.RERANK_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.RERANK_TIMEOUT_MS", 50)

    class SlowReranker(reranker_service.RerankerService):
        async def rerank(self, query, docs, top_n):
            await asyncio.sleep(1.0)  # > 50ms timeout → asyncio.TimeoutError
            return []

    reranker_service.reset_reranker_for_tests()
    reranker_service._reranker_singleton = SlowReranker()

    fake_rows = [(1, 0.1), (2, 0.2), (3, 0.3)]
    with patch("app.services.kb_retrieval.sa_text"), \
         patch.object(session, "execute") as exec_mock:
        exec_mock.return_value.fetchall.return_value = fake_rows

        result = await _vector_search(
            session=session,
            query="hello",
            qvec=[0.0] * 768,
            top_k=2,
            chat_id_filter=None,
            topic_filter=None,
            source_type=None,
            category_filter=None,
            similarity_threshold=0.45,
            customer_id_filter=None,
        )

    assert [kb.id for kb in result] == [1, 2]
