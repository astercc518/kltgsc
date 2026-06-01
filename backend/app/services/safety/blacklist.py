"""L0 keyword/phrase blacklist — first-line cheap filter before any LLM call.

Loads plain-text files from app/data/blacklist/. Each file = one named list.
Lines starting with '#' are comments; blank lines ignored.
Match is case-insensitive substring on the normalized (lower-cased) input.

This layer should have HIGH PRECISION (very few false positives) and is sized
to catch the absolute red lines from Google's Generative AI AUP. L1
(toxic-bert) handles the long tail.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "blacklist"


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
                terms.append(line.lower())
            lists[path.stem] = terms
        return cls(lists)

    def match(self, text: str) -> BlacklistVerdict:
        if not text:
            return BlacklistVerdict(hit=False)
        haystack = text.lower()
        for list_name, terms in self.lists.items():
            for term in terms:
                if term in haystack:
                    return BlacklistVerdict(hit=True, list_name=list_name, term=term)
        return BlacklistVerdict(hit=False)
