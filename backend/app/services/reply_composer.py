"""
ReplyComposer — 三段式回复生成 (Phase 1: KB-only, 无案例库, 无数字一致性)。

Phase 2 升级: 接入 case_studies + 数字一致性反幻觉
Phase 4 升级: 失败转副驾驶 Inbox

参考: spec §6
"""
import logging
import re
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


# ============================================================
# Phase 2a: case_studies + 数字一致性反幻觉
# ============================================================

from app.services.case_study_service import find_top_k_for_topic  # noqa: E402

# 数字 + 量级单位 的提取正则，分两组：
#   _COMPOUND_PATTERNS_NO_SPACE: 无空格的复合 token (100k, 30万 glued)
#   _COMPOUND_PATTERNS_WITH_SPACE: 允许中间有空格 (30 万)
#   _SPECIAL_PATTERNS: T+0, 50%
#   _BARE_FALLBACK: 纯数字 (最后兜底)
#
# 规则: bare N 只在没有 "紧贴" 的 compound 时保留。
#   "100k"  → compound(no-space): keep "100k", drop bare "100"
#   "30 万" → compound(with-space): keep "30万" AND keep bare "30" (space→independent)
_COMPOUND_NO_SPACE = re.compile(r"\d+(?:\.\d+)?[kKmMbB万亿百千]")
_COMPOUND_WITH_SPACE = re.compile(r"\d+(?:\.\d+)?\s+[万亿]")
_SPECIAL = re.compile(r"T\+\d+|\d+(?:\.\d+)?%")
_BARE = re.compile(r"\d+(?:\.\d+)?")


def _normalise(token: str) -> str:
    token = re.sub(r'\s+', '', token)
    return token.replace("K", "k").replace("M", "m").replace("B", "b")


def _extract_numbers(text: str) -> set[str]:
    """
    Extract numbers + magnitude tokens from text, returning a normalised set.

    Key semantics:
    - "100k"  → {"100k"}          (bare "100" suppressed: glued compound)
    - "30 万" → {"30万", "30"}    (bare "30" kept: space-separated compound)
    - "3"     → {"3"}             (bare number, no unit)
    - "T+0"   → {"T+0"}
    - "50%"   → {"50%"}
    """
    if not text:
        return set()

    found: set[str] = set()
    # Spans covered by no-space compound matches (bare numbers at these positions dropped)
    compound_nospace_spans: list[tuple[int, int]] = []

    for m in _COMPOUND_NO_SPACE.finditer(text):
        found.add(_normalise(m.group(0)))
        compound_nospace_spans.append((m.start(), m.end()))

    for m in _COMPOUND_WITH_SPACE.finditer(text):
        found.add(_normalise(m.group(0)))
        # Do NOT record span — bare digit at same position stays

    for m in _SPECIAL.finditer(text):
        found.add(_normalise(m.group(0)))

    # Bare fallback: only add if start position not inside a no-space compound span
    for m in _BARE.finditer(text):
        inside = any(s <= m.start() < e for s, e in compound_nospace_spans)
        if not inside:
            found.add(_normalise(m.group(0)))

    return found


def _numeric_consistency_ok(reply_text: str, sources: list[str]) -> bool:
    """回复里的所有数字都必须能在 sources 任一条里找到 (大小写归一)。"""
    reply_nums = _extract_numbers(reply_text)
    if not reply_nums:
        return True
    source_nums: set[str] = set()
    for s in sources:
        source_nums.update(_extract_numbers(s))
    hallucinated = reply_nums - source_nums
    return len(hallucinated) == 0


def find_case_top_k(*, session, customer_id, topic, k=2) -> list:
    """薄包装方便 mock"""
    return find_top_k_for_topic(
        session=session, customer_id=customer_id, topic=topic, k=k,
    )


def _build_prompt_phase2a(
    source_text: str, solution_topic: str,
    kb_hits: list[dict], case_top1,
) -> str:
    kb_block = "\n".join(f"- {h['text']}" for h in kb_hits) if kb_hits else "(无)"
    if case_top1 is not None:
        case_block = (
            f"问题: {case_top1.problem}\n"
            f"方案: {case_top1.solution}\n"
            f"效果: {case_top1.outcome}\n"
            f"金额/规模: {case_top1.deal_size or '未填'}"
        )
    else:
        case_block = "(无匹配案例, 仅用 KB 概述)"

    return f"""你扮演 TG 群里的真人销售。看到陌生人发: 「{source_text}」

你建议的方案主题: {solution_topic}

业务知识 (KB top 3):
{kb_block}

你最近的真实成交案例 (必须使用其中的具体数字, 不要编):
{case_block}

请回复 3 句话, 不超 {MAX_REPLY_LENGTH} 中文字:
1. 一句话方案: 针对对方需求点提出做法
2. 一句话案例: 引用上面真实案例 + 具体数字 (没案例时用一句话效果泛述)
3. 一句话引导: 自然提议私聊深聊

禁止:
- "作为 AI" / "我是助手" / "作为大模型"
- "+V" / "加我 V" / "扫码" / "微信"
- 编造任何未在案例 / KB 出现的数字
- 超过 {MAX_REPLY_LENGTH} 字
- 模板化套话
- 超过 1 个 emoji
"""


async def compose_reply_phase2a(
    *, customer_id: int, source_text: str, solution_topic: str, session,
) -> Optional[str]:
    """
    Phase 2a 三段式: KB + 案例 + 数字一致性反幻觉。

    Args:
        session: SQLModel Session (用于 case_studies + KB 查询)

    Returns:
        str: 最终回复
        None: 失败 (status=failed 由调用方写; Phase 4 改 suggested)
    """
    kb_hits = await kb_retrieve_top_k(customer_id, solution_topic, k=3)
    cases = find_case_top_k(
        session=session, customer_id=customer_id, topic=solution_topic, k=2,
    )
    case_top1 = cases[0] if cases else None

    prompt = _build_prompt_phase2a(source_text, solution_topic, kb_hits, case_top1)

    # 构造 sources 列表供数字一致性检查
    sources = [h.get("text", "") for h in kb_hits]
    if case_top1:
        sources.extend([
            case_top1.problem or "", case_top1.solution or "",
            case_top1.outcome or "", case_top1.deal_size or "",
        ])

    for attempt in range(MAX_RETRIES + 1):
        raw = await llm_generate_reply(prompt)
        filtered = _anti_hallucination_filter(raw)
        if filtered and _passes_filter(filtered) and _numeric_consistency_ok(filtered, sources):
            # 更新 case.last_used_at (best effort, 不阻塞)
            if case_top1:
                try:
                    from datetime import datetime, timezone
                    case_top1.last_used_at = datetime.now(timezone.utc)
                    session.add(case_top1)
                    session.commit()
                except Exception:
                    logger.warning("failed to update case.last_used_at, ignoring")
            return filtered
        logger.info(
            "phase2a compose attempt %d/%d failed (exposure/length/numeric)",
            attempt + 1, MAX_RETRIES + 1,
        )

    return None
