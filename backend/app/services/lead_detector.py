"""
LeadDetector — 群消息业务线索三层过滤。

Phase 1: 仅实现 Layer 1 (keyword_filters)
Phase 2: 加 Layer 2 (ICP embedding) + Layer 3 (LLM scoring)

参考: spec §3
"""
from typing import Optional


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
