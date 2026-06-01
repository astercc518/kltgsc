"""Combined L0 + L1 gate. Single chokepoint in front of every LLM call.

L0 (Blacklist) runs first — cheap substring match against red-line keywords.
L1 (Moderator) runs only if L0 lets the text through — multi-dim toxic-bert
scoring.

evaluate() returns a SafetyVerdict that downstream routing (Task 3.x) reads:
- blocked=True → refuse the call entirely
- avoid_vertex=True → route to fallback provider (DeepSeek), not Vertex
- otherwise → clean, route to default provider
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.services.safety.blacklist import Blacklist
from app.services.safety.moderation import Moderator, ModerationVerdict


@dataclass
class SafetyVerdict:
    blocked: bool
    block_layer: Optional[str]      # "L0" | "L1" | None
    blacklist_list: Optional[str]   # set when block_layer == "L0"
    blacklist_term: Optional[str]
    moderation: Optional[ModerationVerdict]  # set whenever L1 ran
    avoid_vertex: bool              # True iff L0 hit OR L1 said grey/red

    @property
    def moderation_score(self) -> Optional[float]:
        if self.moderation is None:
            return None
        _, val = self.moderation.score.max_dim()
        return val

    @property
    def max_dim(self) -> Optional[str]:
        if self.moderation is None:
            return None
        name, _ = self.moderation.score.max_dim()
        return name


class SafetyGate:
    def __init__(self, blacklist: Optional[Blacklist] = None,
                 moderator: Optional[Moderator] = None):
        self.blacklist = blacklist or Blacklist.load_default()
        self.moderator = moderator or Moderator()

    def evaluate(self, text: str) -> SafetyVerdict:
        bl = self.blacklist.match(text)
        if bl.hit:
            return SafetyVerdict(
                blocked=True, block_layer="L0",
                blacklist_list=bl.list_name, blacklist_term=bl.term,
                moderation=None, avoid_vertex=True,
            )
        mv = self.moderator.evaluate(text)
        return SafetyVerdict(
            blocked=mv.blocked,
            block_layer=("L1" if mv.blocked else None),
            blacklist_list=None, blacklist_term=None,
            moderation=mv,
            avoid_vertex=mv.avoid_vertex,
        )
