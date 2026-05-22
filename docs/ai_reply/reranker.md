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
