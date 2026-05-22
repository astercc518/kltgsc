# RAG Reranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cross-encoder reranker as an optional post-step to pgvector retrieval in [kb_retrieval.py](../../../backend/app/services/kb_retrieval.py), so that the top-k passed to the LLM is precision-reordered instead of relying solely on cosine distance.

**Architecture:** Introduce a `RerankerService` abstraction with a single `BGEReranker` implementation backed by `fastembed`'s ONNX runtime (no torch dependency). Default to **disabled** (`RERANK_ENABLED=False`) so the change is a no-op until ops flips the flag. When enabled, `_vector_search` fetches `top_k * RERANK_CANDIDATE_MULTIPLIER` (default 5) candidates from pgvector, runs them through the reranker, and returns the top-k by rerank score. Any reranker failure (timeout, model load error, exception) is caught and the original cosine order is returned — retrieval never breaks.

**Tech Stack:**
- `fastembed >= 0.4.0` — ONNX cross-encoder, ~80 MB INT8 model, no torch
- Model: `Xenova/ms-marco-MiniLM-L-6-v2` (test default) and `BAAI/bge-reranker-v2-m3` (production default, multilingual incl. Chinese)
- pytest + pytest-asyncio (existing test setup)
- Settings via `pydantic_settings.BaseSettings` (existing [config.py](../../../backend/app/core/config.py))

---

## Decision Log

### BGE local vs Cohere Rerank API

| Dimension | BGE-v2-m3 via fastembed (chosen) | Cohere Rerank-multilingual-v3 |
|---|---|---|
| Per-query cost @ 1000 customers × 100 retrievals/day | $0 | ~$3/day → ~$1.1k/yr |
| Latency (top-20 candidates, CPU) | 100–250 ms | 80–150 ms + network |
| Memory per worker | ~250 MB resident after model load | 0 |
| External dependency | None (ONNX runtime + HF model download once) | Cohere API key + outage exposure |
| Quality (Chinese/multilingual) | BGE-v2-m3 is SOTA open-source, ≈90% of Cohere v3 on MTEB Chinese rerank | Slightly higher on hard cases |
| Fits codebase posture | ✅ same self-host stance as Vertex Gemini | Adds another vendor |

**Decision:** Ship BGE local. The `RerankerService` interface leaves room for a `CohereReranker` adapter later (NOT built now — YAGNI).

### Cosine threshold interaction

Current code culls candidates with `(1 - distance) < similarity_threshold` and falls back to top-1 if all are culled. When reranker is enabled, we **bypass the cosine threshold** for the pre-fetch (raw top `top_k * multiplier`) and rely on rerank scores for ordering. We still take `top_k` at the end. Rationale: the cosine threshold's job is "kick out obvious garbage", but the reranker is strictly better at that job — keeping both would just discard candidates the reranker might rescue.

### Rollout (after merge)

Phase 1 (week 1): `RERANK_ENABLED=true` on **staging only**, observe latency p95 and KB hit-rate logs.
Phase 2 (week 2): enable for a single canary customer in prod via per-customer override (not implemented in this plan — manual SQL flag if needed).
Phase 3: global enable. Keep `RERANK_ENABLED=false` switch as kill-switch.

---

## File Structure

**Create:**
- `backend/app/services/reranker_service.py` — `RerankerService` interface, `BGEReranker` impl, `get_reranker()` singleton factory
- `backend/tests/test_reranker_service.py` — unit tests for the service (model mocked)
- `backend/tests/test_kb_retrieval_rerank.py` — unit tests for `_vector_search` rerank wiring (DB + reranker mocked)
- `docs/ai_reply/reranker.md` — operator-facing rollout doc

**Modify:**
- `backend/app/core/config.py` — add 4 settings
- `backend/app/services/kb_retrieval.py` — call reranker inside `_vector_search` behind flag
- `backend/requirements.txt` — add `fastembed>=0.4.0`

---

## Task 1: Add reranker config settings

**Files:**
- Modify: `backend/app/core/config.py` (insert new block before `model_config = SettingsConfigDict(...)`, currently the last line of the `Settings` class)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_reranker_config.py`:

```python
"""Smoke test that the reranker settings load with the expected defaults."""
import importlib
import sys


def test_reranker_settings_defaults(monkeypatch):
    # Force a fresh import so default env values take effect (no .env override)
    for key in ("RERANK_ENABLED", "RERANK_MODEL", "RERANK_CANDIDATE_MULTIPLIER", "RERANK_TIMEOUT_MS"):
        monkeypatch.delenv(key, raising=False)
    sys.modules.pop("app.core.config", None)
    import app.core.config as cfg

    s = cfg.Settings()
    assert s.RERANK_ENABLED is False
    assert s.RERANK_MODEL == "BAAI/bge-reranker-v2-m3"
    assert s.RERANK_CANDIDATE_MULTIPLIER == 5
    assert s.RERANK_TIMEOUT_MS == 800


def test_reranker_settings_env_override(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_CANDIDATE_MULTIPLIER", "8")
    sys.modules.pop("app.core.config", None)
    import app.core.config as cfg

    s = cfg.Settings()
    assert s.RERANK_ENABLED is True
    assert s.RERANK_CANDIDATE_MULTIPLIER == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_reranker_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'RERANK_ENABLED'`

- [ ] **Step 3: Add settings to `config.py`**

In [backend/app/core/config.py](../../../backend/app/core/config.py), insert just before `model_config = SettingsConfigDict(...)` (the last line of the `Settings` class):

```python
    # ── RAG Reranker (cross-encoder post-step for kb_retrieval) ──────
    # Default OFF; flip to true after staging validation. See
    # docs/ai_reply/reranker.md for rollout guidance.
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    # Number of pgvector candidates fetched per query = top_k * multiplier
    RERANK_CANDIDATE_MULTIPLIER: int = 5
    # Hard timeout for one rerank call; on timeout we drop back to cosine order
    RERANK_TIMEOUT_MS: int = 800
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_reranker_config.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_reranker_config.py
git commit -m "feat(rag): add reranker settings (disabled by default)"
```

---

## Task 2: Reranker service interface and disabled-path factory

We build the interface and the "off" code path first. The real BGE adapter goes in Task 3.

**Files:**
- Create: `backend/app/services/reranker_service.py`
- Create: `backend/tests/test_reranker_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_reranker_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_reranker_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.reranker_service'`

- [ ] **Step 3: Implement the service module**

Create `backend/app/services/reranker_service.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_reranker_service.py -v`
Expected: 4 passed (the BGE import in `get_reranker` won't trigger because `RERANK_ENABLED` is False)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/reranker_service.py backend/tests/test_reranker_service.py
git commit -m "feat(rag): RerankerService interface + NoopReranker default"
```

---

## Task 3: BGE adapter via fastembed (lazy load + async wrapper)

The ONNX model load is sync and expensive (~1–2 s first call). We load lazily on first `rerank` call and offload `model.rerank` to a threadpool so the asyncio loop stays responsive.

**Files:**
- Create: `backend/app/services/reranker_service_bge.py`
- Modify: `backend/tests/test_reranker_service.py` (append tests for the adapter, model mocked)
- Modify: `backend/requirements.txt` (add `fastembed>=0.4.0`)

- [ ] **Step 1: Add the dependency**

Append to `backend/requirements.txt`:

```
fastembed>=0.4.0
```

- [ ] **Step 2: Install it locally**

Run: `cd backend && pip install 'fastembed>=0.4.0'`
Expected: installs cleanly (fastembed pulls onnxruntime + tokenizers; no torch)

- [ ] **Step 3: Write the failing tests**

Append to `backend/tests/test_reranker_service.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_reranker_service.py -v`
Expected: 3 new tests FAIL with `ModuleNotFoundError: No module named 'app.services.reranker_service_bge'`

- [ ] **Step 5: Implement the BGE adapter**

Create `backend/app/services/reranker_service_bge.py`:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_reranker_service.py -v`
Expected: all 7 tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/reranker_service_bge.py \
        backend/tests/test_reranker_service.py \
        backend/requirements.txt
git commit -m "feat(rag): BGE cross-encoder reranker via fastembed"
```

---

## Task 4: Wire reranker into `_vector_search`

When the reranker is enabled, fetch a wider candidate set, skip the cosine threshold cull, hand candidates to the reranker, and return top_k by rerank score. `_vector_search` becomes `async` (was sync) so we can `await` the reranker — the only caller is `retrieve_relevant_kb`, which is already async.

**Files:**
- Modify: `backend/app/services/kb_retrieval.py` ([_vector_search](../../../backend/app/services/kb_retrieval.py#L125), L125–L186) — make async, add `query` param, add reranker call. Plus call-site update at [L106](../../../backend/app/services/kb_retrieval.py#L106).
- Create: `backend/tests/test_kb_retrieval_rerank.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kb_retrieval_rerank.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_kb_retrieval_rerank.py -v`
Expected: FAIL — most likely `TypeError: _vector_search() got an unexpected keyword argument 'query'`, or `TypeError: object list can't be used in 'await' expression` (because `_vector_search` is currently sync).

- [ ] **Step 3: Add the rerank helper and update `_vector_search` to async**

Edit [backend/app/services/kb_retrieval.py](../../../backend/app/services/kb_retrieval.py).

**3a.** Add `import asyncio` at the top of the file (alongside the other stdlib imports).

**3b.** Just below the `_UNSCOPED = object()` sentinel (near L62), add this helper:

```python
async def _rerank_with_timeout(reranker, query: str, docs, top_k: int):
    """Call reranker.rerank with the configured timeout. Raises on timeout."""
    from app.core.config import settings
    timeout_s = settings.RERANK_TIMEOUT_MS / 1000.0
    return await asyncio.wait_for(
        reranker.rerank(query, docs, top_n=top_k),
        timeout=timeout_s,
    )
```

**3c.** Replace the existing `_vector_search` function (currently at L125–L186) with the async version below. **Note the new signature:** `async def`, and a new `query: str` parameter inserted right after `session`.

```python
async def _vector_search(
    session: Session,
    query: str,
    qvec: List[float],
    top_k: int,
    chat_id_filter: Optional[int],
    topic_filter: Optional[str],
    source_type: Optional[str],
    category_filter: Optional[str],
    similarity_threshold: float,
    customer_id_filter,
) -> List[KnowledgeBase]:
    from app.core.config import settings
    from app.services.reranker_service import get_reranker, NoopReranker

    reranker = get_reranker()
    rerank_active = not isinstance(reranker, NoopReranker)

    # When the reranker is on, fetch a wider net and skip the cosine
    # threshold cull (the reranker is strictly better at deciding what
    # to keep). Default multiplier 5 → top_k=5 fetches 25 candidates.
    multiplier = settings.RERANK_CANDIDATE_MULTIPLIER if rerank_active else 2
    fetch_limit = top_k * multiplier

    where_clauses = ["embedding IS NOT NULL"]
    params: dict = {"qvec": str(qvec), "top_k": fetch_limit}

    if customer_id_filter is not None:
        where_clauses.append("(customer_id = :customer_id OR customer_id IS NULL)")
        params["customer_id"] = customer_id_filter
    if source_type:
        where_clauses.append("source_type = :source_type")
        params["source_type"] = source_type
    if chat_id_filter is not None:
        where_clauses.append("source_chat_id = :chat_id")
        params["chat_id"] = chat_id_filter
    if topic_filter:
        where_clauses.append("qa_topic = :topic")
        params["topic"] = topic_filter
    if category_filter:
        where_clauses.append("category = :category")
        params["category"] = category_filter

    where_sql = " AND ".join(where_clauses)
    sql = sa_text(
        f"""
        SELECT id, (embedding <=> CAST(:qvec AS vector)) AS distance
        FROM ai_knowledge_base
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :top_k
        """
    )

    rows = session.execute(sql, params).fetchall()
    if not rows:
        return []

    if rerank_active:
        candidate_ids = [r[0] for r in rows]
    else:
        # Legacy path: cosine threshold cull, fall back to top-1 if all culled.
        candidate_ids = [r[0] for r in rows if (1 - float(r[1])) >= similarity_threshold]
        if not candidate_ids:
            candidate_ids = [rows[0][0]]
        candidate_ids = candidate_ids[:top_k]

    kbs_unordered = session.exec(
        select(KnowledgeBase).where(KnowledgeBase.id.in_(candidate_ids))
    ).all()
    by_id = {kb.id: kb for kb in kbs_unordered}
    candidates = [by_id[i] for i in candidate_ids if i in by_id]

    if not rerank_active or not candidates:
        return candidates

    # Prefer qa_answer (short, dense) over content for reranker scoring.
    docs = [
        (kb.qa_answer or kb.content or kb.name or "").strip()[:1000]
        for kb in candidates
    ]

    try:
        ranked = await _rerank_with_timeout(reranker, query, docs, top_k)
    except Exception as e:
        # Timeout, model load failure, anything — retrieval must not break.
        logger.error(f"Reranker failed, returning cosine order: {e}")
        return candidates[:top_k]

    return [candidates[idx] for idx, _score in ranked]
```

**3d.** Update the only call site in `retrieve_relevant_kb` (around [L106](../../../backend/app/services/kb_retrieval.py#L106)). Replace:

```python
                return _vector_search(
                    session, qvec, top_k,
                    chat_id_filter, topic_filter, source_type, category_filter,
                    similarity_threshold, customer_id_filter,
                )
```

with:

```python
                return await _vector_search(
                    session, query, qvec, top_k,
                    chat_id_filter, topic_filter, source_type, category_filter,
                    similarity_threshold, customer_id_filter,
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_kb_retrieval_rerank.py tests/test_reranker_service.py tests/test_reranker_config.py -v`
Expected: all tests pass (4 in rerank, 7 in service, 2 in config)

- [ ] **Step 5: Smoke-check existing callers still work**

Run: `cd backend && pytest tests/ -v`
Expected: no regressions. The two real callers of `retrieve_relevant_kb` are [ai_reply_service.py:255](../../../backend/app/services/ai_reply_service.py#L255) and [conversation_director.py:284](../../../backend/app/services/conversation_director.py#L284); both already `await retrieve_relevant_kb(...)`, so the public interface is unchanged.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/kb_retrieval.py backend/tests/test_kb_retrieval_rerank.py
git commit -m "feat(rag): wire reranker into _vector_search behind RERANK_ENABLED"
```

---

## Task 5: Operator-facing rollout doc

The code change is invisible until ops flips `RERANK_ENABLED=true`. Document the why, the rollout phases, the kill-switch, and the metrics to watch.

**Files:**
- Create: `docs/ai_reply/reranker.md`

- [ ] **Step 1: Write the doc**

Create `docs/ai_reply/reranker.md`:

```markdown
# KB Retrieval Reranker

The KB retrieval path ([backend/app/services/kb_retrieval.py](../../backend/app/services/kb_retrieval.py))
supports an optional cross-encoder reranker that runs after pgvector
cosine retrieval to reorder candidates by precision.

## Why

pgvector cosine retrieval ranks by embedding similarity, which is fast
but lossy. A cross-encoder scores `(query, doc)` pairs directly and
typically lifts precision@5 by 15–30 % on Chinese KB queries. We pay
the cost only when `RERANK_ENABLED=true`.

## How it works

When enabled, `_vector_search` fetches `top_k * RERANK_CANDIDATE_MULTIPLIER`
candidates from pgvector (default 5× = 25 for top-5), skips the cosine
similarity threshold, and passes the candidates to
`BGEReranker.rerank()`. The reranker returns the top-k by rerank score.

If the reranker raises or exceeds `RERANK_TIMEOUT_MS`, retrieval falls
back to cosine order — KB retrieval never breaks on a reranker fault.

## Settings

| Setting | Default | Effect |
|---|---|---|
| `RERANK_ENABLED` | `false` | Master switch. Off → no reranker code runs at all. |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | HuggingFace model id supported by `fastembed.rerank.cross_encoder.TextCrossEncoder`. |
| `RERANK_CANDIDATE_MULTIPLIER` | `5` | Candidates pulled = top_k × this. Higher = better recall, slower. |
| `RERANK_TIMEOUT_MS` | `800` | Per-call hard timeout; cosine fallback on exceed. |

## Rollout phases

1. **Staging** — set `RERANK_ENABLED=true`; watch reranker latency p95
   (target < 300 ms) and KB hit-rate logs for 3–7 days.
2. **Canary** — enable for one customer in prod. (No per-customer flag
   exists yet; do this with a small wrapper around `get_reranker()` if
   needed, or just go to phase 3 if staging looks clean.)
3. **Global** — flip the prod env var. Keep the switch available as a
   kill-switch.

## Kill-switch

Set `RERANK_ENABLED=false` and restart the affected processes
(listener workers + the FastAPI app). Cached singleton is cleared on
restart; no DB change needed.

## First-run model download

The first `rerank()` call on each worker process downloads ~80 MB of
ONNX weights to `~/.cache/fastembed/`. Pre-warm in prod by hitting any
endpoint that triggers KB retrieval after enabling the flag — first
call will be 1–2 s slower.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ai_reply/reranker.md
git commit -m "docs(rag): reranker rollout guide"
```

---

## Done criteria

- [ ] All tests in `tests/test_reranker_config.py`, `tests/test_reranker_service.py`, `tests/test_kb_retrieval_rerank.py` pass.
- [ ] `pytest tests/ -v` shows no regressions on existing suites.
- [ ] `git grep -n "RERANK_ENABLED"` returns exactly: config.py (definition), reranker_service.py (read), kb_retrieval.py (read indirectly through reranker), reranker.md (docs), and the three test files.
- [ ] `RERANK_ENABLED=false` is the merged default — production behavior is unchanged until ops flips the flag.
