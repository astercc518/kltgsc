"""
LeadDetector — 群消息业务线索三层过滤。

Phase 1: 仅实现 Layer 1 (keyword_filters)
Phase 2: 加 Layer 2 (ICP embedding) + Layer 3 (LLM scoring)
Phase 2a Task 5: run_all_layers orchestrator — Layer 1 → 2 → 3, 早返 + borderline 标记

参考: spec §3
"""
import logging
import math
from typing import Optional

from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)


def layer1_keyword_match(
    text: str,
    filters: Optional[dict],
    legacy_keyword: Optional[str] = None,
) -> dict:
    """
    Layer 1: include/exclude 关键词过滤 (大小写不敏感)。

    Args:
        text: 群消息原文
        filters: {"include": [...], "exclude": [...], "mode": "any"|"all"}
                 None → 降级用 legacy_keyword
        legacy_keyword: monitor.keyword 旧字段, 兼容路径

    Returns:
        {"pass": bool, "matched": [str], "excluded": [str]}
    """
    text_lower = text.lower()

    if filters is None:
        if not legacy_keyword:
            return {"pass": False, "matched": [], "excluded": []}
        kw_lower = legacy_keyword.lower()
        hit = kw_lower in text_lower
        return {
            "pass": hit,
            "matched": [legacy_keyword] if hit else [],
            "excluded": [],
        }

    include = filters.get("include", []) or []
    exclude = filters.get("exclude", []) or []
    mode = filters.get("mode", "any")

    # exclude 优先
    excluded_hits = [w for w in exclude if w.lower() in text_lower]
    if excluded_hits:
        return {"pass": False, "matched": [], "excluded": excluded_hits}

    if not include:
        return {"pass": False, "matched": [], "excluded": []}

    matched = [w for w in include if w.lower() in text_lower]

    if mode == "all":
        passed = len(matched) == len(include)
    else:  # any
        passed = len(matched) > 0

    return {"pass": passed, "matched": matched, "excluded": []}


# ---------------------------------------------------------------------------
# Layer 2: ICP embedding cosine similarity
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list, b: list) -> float:
    """计算两个向量的余弦相似度. 0 向量返回 0.0。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


BORDERLINE_BAND = 0.05  # 阈值下 0.05 内算 borderline


async def layer2_icp_similarity(
    *, session, text: str, icp_embedding: Optional[list], threshold: float,
) -> dict:
    """
    Layer 2: 消息 vs 客户 ICP embedding 余弦相似度。

    Returns:
        {"pass": bool, "similarity": float | None,
         "degraded": bool, "borderline": bool}

    pass=True 三种情况:
      - 相似度 >= threshold (正常通过)
      - icp_embedding=None (客户没设画像, 降级跳过该层)
      - 消息 embedding 生成失败 (服务挂, 不阻塞管线)
    """
    if icp_embedding is None:
        return {"pass": True, "similarity": None, "degraded": True, "borderline": False}

    msg_vec = await embed_text(session=session, text=text)
    if msg_vec is None:
        return {"pass": True, "similarity": None, "degraded": True, "borderline": False}

    sim = _cosine_similarity(msg_vec, icp_embedding)
    passed = sim >= threshold
    borderline = (not passed) and (sim >= threshold - BORDERLINE_BAND)
    return {
        "pass": passed, "similarity": sim,
        "degraded": False, "borderline": borderline,
    }


# ---------------------------------------------------------------------------
# Layer 3 helpers: thin wrappers around LLMService + KB retrieval
# (kept as top-level async functions so tests can patch them easily)
# ---------------------------------------------------------------------------

async def _score_lead(*, session, text: str, icp_text, kb_top3: list, recent_context: list) -> dict:
    """薄包装 LLMService.score_lead_message, 方便 mock。"""
    from app.services.llm import LLMService  # local import avoids circular import
    svc = LLMService(session)
    return await svc.score_lead_message(
        text=text, icp_text=icp_text, kb_top3=kb_top3, recent_context=recent_context,
    )


async def _fetch_kb_top3(*, session, customer_id, query: str) -> list:
    """从 KB 取 top 3, 返回 [{"text": str, "score": float}, ...]。

    retrieve_relevant_kb 签名 (验证后):
        async def retrieve_relevant_kb(session, query, top_k=5, customer_id_filter=_UNSCOPED, ...) -> List[KnowledgeBase]
    返回的 KnowledgeBase 对象有 .content 字段。
    """
    if not query:
        return []
    try:
        from app.services.kb_retrieval import retrieve_relevant_kb  # local import
        rows = await retrieve_relevant_kb(
            session, query, top_k=3, customer_id_filter=customer_id,
        )
        return [{"text": r.content, "score": 1.0} for r in (rows or [])]
    except Exception:
        logger.exception("_fetch_kb_top3: KB retrieval failed")
        return []


async def _fetch_recent_context(*, session, chat_id: int, before_message_id=None) -> list:
    """从 group_message 取最近群上下文。

    Phase 2a: 简化为空返回, Phase 3 再接入 group_message 查询。
    """
    return []


# ---------------------------------------------------------------------------
# Orchestrator: run_all_layers
# ---------------------------------------------------------------------------

async def run_all_layers(
    *, session, customer, monitor, text: str, chat_id: int,
) -> dict:
    """
    跑 Layer 1 → 2 → 3，早返 + borderline 标记。

    Args:
        session:  DB session
        customer: Customer ORM 对象 (需有 icp_profile_embedding, icp_profile_text,
                  lead_detector_thresholds, id)
        monitor:  GroupMonitor ORM 对象 (需有 keyword_filters, keyword)
        text:     群消息原文
        chat_id:  Telegram chat_id (用于上下文查询)

    Returns:
        pass=True 时:
            {"pass": True, "layer1_matched": [...],
             "layer2_similarity": float | None, "layer3": {...}, "borderline": False}

        pass=False 时:
            {"pass": False, "skip_reason": "layer1_miss"|"layer2_miss"|"layer3_miss",
             "layer1_matched": [...], "layer2_similarity": float | None,
             "layer3": dict | None, "borderline": bool}
    """
    thresholds = customer.lead_detector_thresholds or {
        "layer2_sim": 0.55,
        "layer3_score": 60,
        "layer3_confidence": 0.7,
    }

    # ------------------------------------------------------------------
    # Layer 1: keyword match
    # ------------------------------------------------------------------
    l1 = layer1_keyword_match(
        text,
        filters=getattr(monitor, "keyword_filters", None),
        legacy_keyword=getattr(monitor, "keyword", None),
    )
    if not l1["pass"]:
        return {
            "pass": False,
            "skip_reason": "layer1_miss",
            "layer1_matched": [],
            "layer2_similarity": None,
            "layer3": None,
            "borderline": False,
        }

    # ------------------------------------------------------------------
    # Layer 2: ICP embedding similarity
    # ------------------------------------------------------------------
    l2 = await layer2_icp_similarity(
        session=session,
        text=text,
        icp_embedding=customer.icp_profile_embedding,
        threshold=thresholds.get("layer2_sim", 0.55),
    )
    if not l2["pass"]:
        # degraded=True means pass=True, so here pass=False means genuine miss
        return {
            "pass": False,
            "skip_reason": "layer2_miss",
            "layer1_matched": l1["matched"],
            "layer2_similarity": l2["similarity"],
            "layer3": None,
            "borderline": l2.get("borderline", False),
        }

    # ------------------------------------------------------------------
    # Layer 3: LLM scoring
    # ------------------------------------------------------------------
    kb_top3 = await _fetch_kb_top3(
        session=session, customer_id=customer.id, query=text,
    )
    recent_ctx = await _fetch_recent_context(session=session, chat_id=chat_id)

    l3 = await _score_lead(
        session=session,
        text=text,
        icp_text=getattr(customer, "icp_profile_text", None),
        kb_top3=kb_top3,
        recent_context=recent_ctx,
    )

    score_thr = thresholds.get("layer3_score", 60)
    conf_thr = thresholds.get("layer3_confidence", 0.7)
    score = l3["score"]
    conf = l3["confidence"]

    passed = score >= score_thr and conf >= conf_thr

    borderline = False
    if not passed:
        # borderline: score 落在 [score_thr-5, score_thr) 或 confidence 落在 [conf_thr-0.1, conf_thr)
        borderline = (
            (score_thr - 5 <= score < score_thr)
            or (conf_thr - 0.1 <= conf < conf_thr)
        )

    if not passed:
        return {
            "pass": False,
            "skip_reason": "layer3_miss",
            "layer1_matched": l1["matched"],
            "layer2_similarity": l2["similarity"],
            "layer3": l3,
            "borderline": borderline,
        }

    return {
        "pass": True,
        "layer1_matched": l1["matched"],
        "layer2_similarity": l2["similarity"],
        "layer3": l3,
        "borderline": False,
    }
