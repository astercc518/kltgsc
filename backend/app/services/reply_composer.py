"""
ReplyComposer — 三段式回复生成 (Phase 1: KB-only, 无案例库, 无数字一致性)。

Phase 2 升级: 接入 case_studies + 数字一致性反幻觉
Phase 4 升级: 失败转副驾驶 Inbox

参考: spec §6
"""
import logging
from typing import Optional

from sqlmodel import Session
from app.core.db import engine
from app.services.kb_retrieval import retrieve_relevant_kb
from app.services.llm import LLMService
from app.services.shill_dispatcher import _anti_hallucination_filter

logger = logging.getLogger(__name__)

MAX_REPLY_LENGTH = 80
MAX_RETRIES = 2

# 身份暴露词: 直接导致整条回复作废 (same as HALLUCINATION_RE in shill_dispatcher)
IDENTITY_EXPOSURE_PATTERNS = [
    "作为 AI", "我是助手", "作为大模型",
]

# 联系方式暴露词: strip 掉片语后保留剩余文本
CONTACT_EXPOSURE_PATTERNS = [
    "+V", "加我 V", "加微信", "扫码", "扫一扫",
]


async def kb_retrieve_top_k(customer_id: int, query: str, k: int = 3) -> list[dict]:
    """
    薄包装, 方便 mock。

    Bridges: retrieve_relevant_kb(session, query, top_k, customer_id_filter)
    Returns List[KnowledgeBase] — converted to List[{"text": str, "score": float}].
    Score is 1.0 (phase 1; phase 2 will surface cosine similarity).
    """
    with Session(engine) as session:
        kb_items = await retrieve_relevant_kb(
            session,
            query,
            top_k=k,
            customer_id_filter=customer_id,
        )
    return [{"text": item.content, "score": 1.0} for item in kb_items]


async def llm_generate_reply(prompt: str) -> Optional[str]:
    """
    薄包装。

    Bridges: LLMService(session).generate(prompt, source="reply_composer")
    Returns str | None (None when LLM client not configured).
    """
    with Session(engine) as session:
        llm = LLMService(session)
        result = await llm.generate(prompt, source="reply_composer")
    return result or ""


def _build_prompt(source_text: str, solution_topic: str, kb_hits: list[dict]) -> str:
    kb_block = "\n".join(f"- {h['text']}" for h in kb_hits) if kb_hits else "(无)"
    return f"""你扮演一个 TG 群里的真人销售。看到陌生人发: 「{source_text}」

你建议谈论的方案主题: {solution_topic}

你的业务知识 (来自 KB):
{kb_block}

请回复 3 句话, 不超 {MAX_REPLY_LENGTH} 中文字:
1. 一句话方案: 针对对方需求点提出做法
2. 一句话效果: 提及业务效果 (Phase 1 可泛说, Phase 2 接入真实案例)
3. 一句话引导: 自然提议私聊深聊

禁止:
- 出现"作为 AI"/"我是助手"/"作为大模型"等暴露词
- 出现"+V"/"加我 V"/"扫码"/"微信"
- 超过 {MAX_REPLY_LENGTH} 字
- 模板化套话
- 超过 1 个 emoji
"""


def _has_identity_exposure(text: str) -> bool:
    """Return True if text contains identity-revealing phrases (whole reply must be discarded)."""
    return any(p in text for p in IDENTITY_EXPOSURE_PATTERNS)


def _strip_contact_exposure(text: str) -> str:
    """Strip contact-exposure fragments (加我 +V, 扫码 etc.) from text, keep the rest."""
    for pattern in CONTACT_EXPOSURE_PATTERNS:
        # Remove the pattern and any surrounding punctuation / whitespace
        import re
        text = re.sub(
            r'[,，\s]*' + re.escape(pattern) + r'[,，\s]*',
            ' ',
            text,
        ).strip()
    return text


def _passes_filter(text: str) -> bool:
    if _has_identity_exposure(text):
        return False
    if len(text) > MAX_REPLY_LENGTH:
        return False
    return True


async def compose_reply_phase1(
    *,
    customer_id: int,
    source_text: str,
    solution_topic: str,
) -> Optional[str]:
    """
    生成三段式回复; 反幻觉 2 次失败返回 None。

    Returns:
        str: 最终回复
        None: 失败 (上层置 status=failed, Phase 4 改为 status=suggested)
    """
    kb_hits = await kb_retrieve_top_k(customer_id, solution_topic, k=3)
    prompt = _build_prompt(source_text, solution_topic, kb_hits)

    for attempt in range(MAX_RETRIES + 1):
        raw = await llm_generate_reply(prompt)
        # Step 1: shill_dispatcher hallucination guard (identity patterns → empty str)
        filtered = _anti_hallucination_filter(raw)
        # Step 2: strip contact-exposure fragments (加我 V, +V, 扫码 …)
        filtered = _strip_contact_exposure(filtered)
        if filtered and _passes_filter(filtered):
            return filtered
        logger.info(
            "reply_composer attempt %d/%d failed filter for customer %s",
            attempt + 1, MAX_RETRIES + 1, customer_id,
        )

    return None
