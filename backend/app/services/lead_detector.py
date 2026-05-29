"""
LeadDetector — 群消息业务线索三层过滤。

Phase 1: 仅实现 Layer 1 (keyword_filters)
Phase 2: 加 Layer 2 (ICP embedding) + Layer 3 (LLM scoring)

参考: spec §3
"""
import math
from typing import Optional

from app.services.embedding_service import embed_text


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


def layer2_icp_similarity(
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

    msg_vec = embed_text(session=session, text=text)
    if msg_vec is None:
        return {"pass": True, "similarity": None, "degraded": True, "borderline": False}

    sim = _cosine_similarity(msg_vec, icp_embedding)
    passed = sim >= threshold
    borderline = (not passed) and (sim >= threshold - BORDERLINE_BAND)
    return {
        "pass": passed, "similarity": sim,
        "degraded": False, "borderline": borderline,
    }
