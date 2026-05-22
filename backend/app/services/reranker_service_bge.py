"""
BGE cross-encoder reranker backed by fastembed (ONNX, no torch).

Model is downloaded on first use (~80 MB INT8 cache under
~/.cache/fastembed) and held in memory for the process lifetime.
The rerank call is sync; we offload to a threadpool so the asyncio
loop stays responsive.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Tuple

from app.services.reranker_service import RerankerService

logger = logging.getLogger(__name__)


class BGEReranker(RerankerService):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None  # lazy; loaded on first rerank() call
        self._load_lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return
            # fastembed import is local so module import stays cheap for
            # tests / workers that never use the reranker.
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            def _build() -> "TextCrossEncoder":
                return TextCrossEncoder(model_name=self.model_name)

            logger.info(f"Loading BGE reranker model: {self.model_name}")
            self._model = await asyncio.to_thread(_build)
            logger.info(f"BGE reranker ready: {self.model_name}")

    async def rerank(
        self,
        query: str,
        docs: List[str],
        top_n: int,
    ) -> List[Tuple[int, float]]:
        if not docs:
            return []

        await self._ensure_loaded()

        def _score() -> List[float]:
            # fastembed.rerank returns a generator of one float per doc,
            # in input order.
            return list(self._model.rerank(query, docs))

        scores = await asyncio.to_thread(_score)
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda t: t[1], reverse=True)
        return indexed[:top_n]
