"""L0 keyword/phrase blacklist — first-line cheap filter before any LLM call.

Loads plain-text files from app/data/blacklist/. Each file = one named list.
Lines starting with '#' are comments; blank lines ignored.
Match is case-insensitive substring on the normalized input.

Normalization (applied symmetrically at load + match time):
  1. NFKC — folds full-width Latin (ｃｈｉｌｄ → child), ligatures, etc.
  2. casefold — Unicode-aware lowercase (handles ß → ss).
  3. strip zero-width chars (U+200B/200C/200D/FEFF) — NFKC does NOT remove
     these, so we strip them explicitly to defeat "child<ZWSP>porn" tricks.
  4. collapse runs of any whitespace (tabs, newlines, NBSP after NFKC) to
     a single space.

This layer should have HIGH PRECISION (very few false positives) and is sized
to catch the absolute red lines from Google's Generative AI AUP. L1
(toxic-bert) handles the long tail.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "blacklist"

# Zero-width / BOM chars that NFKC leaves alone but obvious bypass vectors.
_ZW_CHARS = "​‌‍﻿"
_ZW_RE = re.compile(f"[{_ZW_CHARS}]")
_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Normalize text for blacklist comparison.

    Order matters: NFKC first (so full-width spaces become ASCII space and
    get caught by the whitespace collapse), then casefold, then drop
    zero-width chars (NFKC does not), then collapse whitespace runs.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    text = _ZW_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


@dataclass
class BlacklistVerdict:
    hit: bool
    list_name: Optional[str] = None
    term: Optional[str] = None


class Blacklist:
    def __init__(self, lists: Dict[str, List[str]]):
        self.lists = lists

    @classmethod
    def load_default(cls) -> "Blacklist":
        return cls.load_from_dir(DEFAULT_DATA_DIR)

    @classmethod
    def load_from_dir(cls, data_dir: Path) -> "Blacklist":
        lists: Dict[str, List[str]] = {}
        if not data_dir.exists():
            return cls(lists)
        for path in sorted(data_dir.glob("*.txt")):
            terms: List[str] = []
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                normalized = _normalize(line)
                if normalized:
                    terms.append(normalized)
            lists[path.stem] = terms
        return cls(lists)

    def match(self, text: str) -> BlacklistVerdict:
        if not text:
            return BlacklistVerdict(hit=False)
        haystack = _normalize(text)
        if not haystack:
            return BlacklistVerdict(hit=False)
        for list_name, terms in self.lists.items():
            for term in terms:
                if term in haystack:
                    return BlacklistVerdict(hit=True, list_name=list_name, term=term)
        return BlacklistVerdict(hit=False)
