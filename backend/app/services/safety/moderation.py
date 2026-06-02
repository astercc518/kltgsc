"""L1 multilingual toxicity moderation wrapper.

Wraps `onnx-community/bert-multilingual-toxicity-classifier-ONNX` (an ONNX
export of `textdetox/bert-multilingual-toxicity-classifier`) with a small
threshold-based tiering layer:

  - clean: pass through to Vertex/LLM normally
  - grey:  route AWAY from Vertex (use safer fallback), but don't block
  - red:   block outright, return canned safe-decline

The model is a single-label binary classifier (toxic / not-toxic) covering
15 languages including Chinese, with F1 > 0.90 on benchmark datasets. It
exposes 2 logits; we softmax them and take the probability of the toxic
class as the single `toxic` dim.

We collapse the moderation surface to a single product-facing dim:
  toxic  ← softmax(logits)[1]

(Earlier iterations tried a 5-dim schema via `unitary/toxic-bert`, but the
only multilingual options in the wild are binary; collapsing keeps the
shim invisible to downstream `SafetyGate` / `LLMRouter` / `_safety_check`
which only consume `moderation_score` and `max_dim`.)

Inference is PyTorch-free: onnxruntime for the forward pass, transformers
only for the tokenizer, huggingface_hub for the download.

Singleton: first `evaluate()` call downloads + loads the ORT session and
tokenizer behind a threading.Lock; subsequent calls reuse them. Heavy
imports (onnxruntime, numpy, transformers, huggingface_hub) live INSIDE
`_get_session()` so the module is importable in environments without the
ML stack (e.g. unit tests with mocks).
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "toxic_grey": 0.50,   # >= this → route away from Vertex (DeepSeek)
    "toxic_red": 0.85,    # >= this → block entirely
}

_DIMS: Tuple[str, ...] = ("toxic",)

_DEFAULT_MODEL_NAME = "onnx-community/bert-multilingual-toxicity-classifier-ONNX"
_DEFAULT_CACHE_DIR = "/app/.cache/toxic-multilingual"

# Module-level singleton state for ORT session + tokenizer.
_session = None
_tokenizer = None
_load_lock = threading.Lock()


@dataclass
class ModerationScore:
    toxic: float

    def to_dict(self) -> Dict[str, float]:
        return {"toxic": self.toxic}

    def max_dim(self) -> Tuple[str, float]:
        return ("toxic", self.toxic)


@dataclass
class ModerationVerdict:
    score: ModerationScore
    tier: str  # "clean" | "grey" | "red"
    blocked: bool
    avoid_vertex: bool
    dim_triggered: Optional[str] = None


def _get_session():
    """Lazily download + load the ONNX session and tokenizer.

    Heavy imports are intentionally inside this function so the module
    can be imported (and unit-tested with mocks) in environments where
    onnxruntime / transformers / huggingface_hub aren't installed or
    where we just don't want to pay the import cost.
    """
    global _session, _tokenizer
    if _session is not None and _tokenizer is not None:
        return _session, _tokenizer

    with _load_lock:
        if _session is not None and _tokenizer is not None:
            return _session, _tokenizer

        import onnxruntime as ort  # type: ignore
        from huggingface_hub import hf_hub_download  # type: ignore
        from transformers import AutoTokenizer  # type: ignore

        model_name = os.environ.get("TOXIC_MODEL_NAME", _DEFAULT_MODEL_NAME)
        cache_dir = os.environ.get("TOXIC_MODEL_CACHE", _DEFAULT_CACHE_DIR)
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        onnx_path = hf_hub_download(
            repo_id=model_name,
            filename="onnx/model.onnx",
            cache_dir=cache_dir,
        )
        # The ONNX repo layout may also ship weights as model.onnx_data; hf_hub_download
        # of the main .onnx file is sufficient — ORT picks up sibling files from the
        # cache dir automatically.

        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        sess = ort.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"]
        )

        _session = sess
        _tokenizer = tokenizer
        return _session, _tokenizer


class Moderator:
    """L1 multilingual toxicity classifier with grey/red tiering."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds: Dict[str, float] = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    @classmethod
    def warmup(cls) -> None:
        """Eagerly load the ONNX session + tokenizer.

        Call this at app startup to avoid a multi-second blocking first
        request when the model gets fetched from HuggingFace Hub.
        Idempotent — calling repeatedly is a no-op after the first success.
        """
        _get_session()

    # ------------------------------------------------------------------
    # Inference (mocked in unit tests)
    # ------------------------------------------------------------------
    def _score(self, text: str) -> ModerationScore:
        """Run the ORT session on ``text`` and return a ModerationScore.

        Tests patch this method to avoid downloading / running the model.
        """
        import numpy as np

        sess, tok = _get_session()
        enc = tok(
            text,
            max_length=256,
            padding=True,
            truncation=True,
            return_tensors="np",
        )
        feeds = {
            "input_ids": enc["input_ids"].astype(np.int64),
            "attention_mask": enc["attention_mask"].astype(np.int64),
        }
        # BERT models typically also want token_type_ids; pass zeros if present.
        if "token_type_ids" in enc:
            feeds["token_type_ids"] = enc["token_type_ids"].astype(np.int64)

        outputs = sess.run(None, feeds)
        logits = outputs[0][0]  # shape (2,) for binary classifier

        # Softmax over 2 logits → toxic probability
        e = np.exp(logits - np.max(logits))
        probs = e / e.sum()
        toxic_prob = float(probs[1])  # label 1 = toxic, label 0 = not-toxic

        return ModerationScore(toxic=toxic_prob)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(self, text: str) -> ModerationVerdict:
        if not text or not text.strip():
            return ModerationVerdict(
                score=ModerationScore(toxic=0.0),
                tier="clean",
                blocked=False,
                avoid_vertex=False,
                dim_triggered=None,
            )

        score = self._score(text)
        score_d = score.to_dict()

        # Pass 1: red (block).
        for dim in _DIMS:
            red_key = f"{dim}_red"
            if red_key in self.thresholds and score_d[dim] >= self.thresholds[red_key]:
                return ModerationVerdict(
                    score=score,
                    tier="red",
                    blocked=True,
                    avoid_vertex=True,
                    dim_triggered=dim,
                )

        # Pass 2: grey (avoid Vertex but don't block).
        for dim in _DIMS:
            grey_key = f"{dim}_grey"
            if grey_key in self.thresholds and score_d[dim] >= self.thresholds[grey_key]:
                return ModerationVerdict(
                    score=score,
                    tier="grey",
                    blocked=False,
                    avoid_vertex=True,
                    dim_triggered=dim,
                )

        return ModerationVerdict(
            score=score,
            tier="clean",
            blocked=False,
            avoid_vertex=False,
            dim_triggered=None,
        )
