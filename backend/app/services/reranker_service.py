"""
Cross-encoder reranker for KB retrieval.

The reranker takes a query + a list of candidate documents and returns
the indices reordered by relevance. It is an optional post-step that
runs after pgvector cosine retrieval inside
[kb_retrieval._vector_search](kb_retrieval.py).

The default in production is `NoopReranker` (does nothing). When
`settings.RERANK_ENABLED=true`, `get_reranker()` returns a `BGEReranker`
backed by fastembed's ONNX cross-encoder (see Task 3). All reranker
failures are caught by the caller — retrieval itself must never break.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Module-level singleton so the model is loaded once per worker process.
_reranker_singleton: Optional["RerankerService"] = None


class RerankerService(ABC):
    """Abstract reranker. Implementations must be safe to call concurrently."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        docs: List[str],
        top_n: int,
    ) -> List[Tuple[int, float]]:
        """
        Rerank `docs` against `query` and return the top `top_n` as
        (original_index, score) tuples, highest score first.

        Implementations must:
        - Return [] if `docs` is empty.
        - Never raise on malformed input — caller handles bad data.
        - Respect `top_n` even when len(docs) < top_n (return what's available).
        """


class NoopReranker(RerankerService):
    """Preserves input order. Used when RERANK_ENABLED=false or model load fails."""

    async def rerank(
        self,
        query: str,
        docs: List[str],
        top_n: int,
    ) -> List[Tuple[int, float]]:
        return [(i, 0.0) for i in range(min(top_n, len(docs)))]


def get_reranker() -> RerankerService:
    """Return the process-wide reranker singleton (lazy)."""
    global _reranker_singleton
    if _reranker_singleton is not None:
        return _reranker_singleton

    from app.core.config import settings
    if not settings.RERANK_ENABLED:
        _reranker_singleton = NoopReranker()
        return _reranker_singleton

    # Real adapter wired in Task 3.
    try:
        from app.services.reranker_service_bge import BGEReranker
        _reranker_singleton = BGEReranker(model_name=settings.RERANK_MODEL)
        logger.info(f"Reranker initialized: BGE model={settings.RERANK_MODEL}")
    except Exception as e:
        logger.error(f"Failed to init BGEReranker, falling back to noop: {e}")
        _reranker_singleton = NoopReranker()

    return _reranker_singleton


def reset_reranker_for_tests() -> None:
    """Test helper: clear the singleton so the next get_reranker() rebuilds it."""
    global _reranker_singleton
    _reranker_singleton = None
