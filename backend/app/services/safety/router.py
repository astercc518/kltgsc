"""L2 routing — given a SafetyVerdict, pick a provider and dispatch via LLMService.

Public surface:
    router = LLMRouter(vertex_config_id=..., deepseek_config_id=...)
    out = await router.generate(session, prompt, source="...", ...)

The router owns the SafetyGate evaluation step and the LLMService instantiation.
Callers stop creating LLMService directly — they go through the router. This
guarantees the gate runs and the right config_id is selected.

Routing matrix:
    blocked         → refuse, log, record usage row, return None
    avoid_vertex    → DeepSeek (or refuse if no DeepSeek config — fail-closed)
    clean           → Vertex
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

from sqlmodel import Session, select

from app.models.ai_config import AIConfig
from app.services.llm import LLMService
from app.services.safety.gate import SafetyGate
from app.services.usage_tracker import record_usage

logger = logging.getLogger(__name__)

# Shared gate instance (cheap; reuses blacklist + moderator).
_GATE = SafetyGate()

VERTEX_CONFIG_NAME = "Vertex (default)"
DEEPSEEK_CONFIG_NAME = "DeepSeek-V3 (safety fallback)"


@dataclass
class RouteDecision:
    refuse: bool
    routed_to: Optional[str]   # "vertex" | "deepseek" | None
    config_id: Optional[int]
    reason: str


class LLMRouter:
    def __init__(self, vertex_config_id: Optional[int] = None,
                 deepseek_config_id: Optional[int] = None):
        self.vertex_config_id = vertex_config_id
        self.deepseek_config_id = deepseek_config_id

    @classmethod
    def from_session(cls, session: Session) -> "LLMRouter":
        """Build a router by resolving config IDs from the AIConfig table."""
        def _find(name: str) -> Optional[int]:
            row = session.exec(select(AIConfig).where(AIConfig.name == name)).first()
            return row.id if row else None
        vertex_id = _find(VERTEX_CONFIG_NAME)
        deepseek_id = _find(DEEPSEEK_CONFIG_NAME)
        if vertex_id is None:
            logger.warning(
                f"LLMRouter: no AIConfig row named {VERTEX_CONFIG_NAME!r} — "
                f"clean traffic will fall back to LLMService default config"
            )
        if deepseek_id is None:
            logger.warning(
                f"LLMRouter: no AIConfig row named {DEEPSEEK_CONFIG_NAME!r} — "
                f"grey traffic will fail-closed (refuse) until seeded"
            )
        return cls(vertex_config_id=vertex_id, deepseek_config_id=deepseek_id)

    def decide(self, verdict) -> RouteDecision:
        if verdict.blocked:
            return RouteDecision(
                refuse=True, routed_to=None, config_id=None,
                reason=f"L2 refuse: gate.blocked layer={verdict.block_layer}",
            )
        if verdict.avoid_vertex:
            if self.deepseek_config_id is None:
                # Fail-closed: refuse rather than fall back to Vertex for grey content
                return RouteDecision(
                    refuse=True, routed_to=None, config_id=None,
                    reason="L2 refuse: avoid_vertex but no DeepSeek config",
                )
            return RouteDecision(
                refuse=False, routed_to="deepseek",
                config_id=self.deepseek_config_id,
                reason=(f"L2 deepseek: avoid_vertex "
                        f"(dim={verdict.max_dim} score={verdict.moderation_score})"),
            )
        return RouteDecision(
            refuse=False, routed_to="vertex",
            config_id=self.vertex_config_id,
            reason="L2 vertex: clean",
        )

    async def generate(
        self, session: Session, prompt: str, *,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        source: str = "router",
        account_id: Optional[int] = None,
        persona_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> Optional[str]:
        verdict = _GATE.evaluate(prompt)
        decision = self.decide(verdict)
        logger.info(f"LLMRouter: {decision.reason} source={source}")

        if decision.refuse:
            record_usage(
                provider="router", model="refuse",
                source=f"{source}:routed_refuse",
                input_tokens=0, output_tokens=0,
                account_id=account_id, persona_id=persona_id, chat_id=chat_id,
            )
            return None

        llm = LLMService(db_session=session, config_id=decision.config_id)
        return await llm.get_response(
            prompt=prompt, system_prompt=system_prompt, history=history,
            source=f"{source}:routed_{decision.routed_to}",
            account_id=account_id, persona_id=persona_id, chat_id=chat_id,
        )
