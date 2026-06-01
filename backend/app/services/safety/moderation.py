"""L1 multi-dim toxicity moderation wrapper.

Wraps `unitary/multilingual-toxic-xlm-roberta` (ONNX export) with a small
threshold-based tiering layer:

  - clean: pass through to Vertex/LLM normally
  - grey:  route AWAY from Vertex (use safer fallback), but don't block
  - red:   block outright, return canned safe-decline

The HuggingFace model exposes 6 raw labels:
  ['toxic', 'severe_toxic', 'obscene', 'threat', 'insult', 'identity_hate']

We collapse them into 5 product-facing dims:
  sexual     ← obscene
  violence   ← threat
  hate       ← max(insult, identity_hate)
  self_harm  ← severe_toxic   (proxy; toxic-bert has no dedicated dim)
  political  ← 0.0            (no dim in this model; handled at L0/Vertex routing)

Inference is PyTorch-free: onnxruntime for the forward pass, transformers
only for the tokenizer, huggingface_hub for the download.

Singleton: first `evaluate()` call downloads + loads the ORT session and
tokenizer behind a threading.Lock; subsequent calls reuse them. Heavy
imports (onnxruntime, numpy, transformers, huggingface_hub) live INSIDE
`_get_session()` so the module is importable in environments without the
ML stack (e.g. unit tests with mocks).
"""
from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "sexual_grey": 0.40, "sexual_red": 0.85,
    "violence_grey": 0.50, "violence_red": 0.85,
    "hate_grey": 0.40, "hate_red": 0.80,
    "self_harm_grey": 0.30, "self_harm_red": 0.70,
    "political_grey": 0.50, "political_red": 1.01,  # political: only avoid Vertex; no red
}

_DIMS: Tuple[str, ...] = ("sexual", "violence", "hate", "self_harm", "political")

_DEFAULT_MODEL_NAME = "unitary/multilingual-toxic-xlm-roberta"
_DEFAULT_CACHE_DIR = "/app/.cache/toxic"

# Module-level singleton state for ORT session + tokenizer.
_session = None
_tokenizer = None
_load_lock = threading.Lock()


@dataclass
class ModerationScore:
    sexual: float
    violence: float
    hate: float
    self_harm: float
    political: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "sexual": self.sexual,
            "violence": self.violence,
            "hate": self.hate,
            "self_harm": self.self_harm,
            "political": self.political,
        }

    def max_dim(self) -> Tuple[str, float]:
        d = self.to_dict()
        name = max(d, key=lambda k: d[k])
        return name, d[name]


@dataclass
class ModerationVerdict:
    score: ModerationScore
    tier: str  # "clean" | "grey" | "red"
    blocked: bool
    avoid_vertex: bool
    dim_triggered: Optional[str] = None


def _sigmoid(x: float) -> float:
    # Numerically stable sigmoid for scalar floats.
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


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
    """L1 multi-dim toxicity classifier with grey/red tiering."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds: Dict[str, float] = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    # ------------------------------------------------------------------
    # Inference (mocked in unit tests)
    # ------------------------------------------------------------------
    def _score(self, text: str) -> ModerationScore:
        """Run the ORT session on ``text`` and return a ModerationScore.

        Tests patch this method to avoid downloading / running the model.
        """
        import numpy as np  # local import: keeps module importable without numpy

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
        outputs = sess.run(None, feeds)
        logits = outputs[0][0]  # shape (N,)

        # HF label order: ['toxic', 'severe_toxic', 'obscene', 'threat', 'insult', 'identity_hate']
        probs = [_sigmoid(float(v)) for v in logits]
        # Defensive: pad if model returned fewer dims than expected.
        while len(probs) < 6:
            probs.append(0.0)

        sexual = probs[2]                      # obscene
        violence = probs[3]                    # threat
        hate = max(probs[4], probs[5])         # insult / identity_hate
        self_harm = probs[1]                   # severe_toxic (proxy)
        political = 0.0                        # not modelled here

        return ModerationScore(
            sexual=sexual,
            violence=violence,
            hate=hate,
            self_harm=self_harm,
            political=political,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(self, text: str) -> ModerationVerdict:
        if not text or not text.strip():
            return ModerationVerdict(
                score=ModerationScore(0.0, 0.0, 0.0, 0.0, 0.0),
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
