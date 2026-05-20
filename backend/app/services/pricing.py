"""
LLM / Embedding 价格表（USD per 1M tokens，Vertex AI 2026 价格）。

更新价格只改这一个文件。未列出的模型按 0 计费（会在日志告警）。
"""
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


# USD per 1M tokens
PRICING_USD_PER_1M: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash":     {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro":       {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash":     {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash":     {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":       {"input": 1.25, "output": 5.00},
    "gemini-embedding-001": {"input": 0.15, "output": 0.0},
}

_WARNED_MODELS: set = set()


def calc_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """按 PRICING_USD_PER_1M 计算单次调用成本。未知模型返回 0 并 warn 一次。"""
    rates = PRICING_USD_PER_1M.get(model)
    if rates is None:
        if model not in _WARNED_MODELS:
            logger.warning(
                f"No pricing entry for model={model!r}; cost will be reported as 0. "
                f"Add it to PRICING_USD_PER_1M in pricing.py."
            )
            _WARNED_MODELS.add(model)
        return 0.0
    return (
        input_tokens * rates["input"] / 1_000_000
        + output_tokens * rates["output"] / 1_000_000
    )


def estimate_embedding_tokens(text: str) -> int:
    """
    Embedding token 数 ≈ char_count / 4（英语）或 / 1.5（中文）。
    Gemini 计费按 char 数粗略可以这么估，足够本地估算。
    """
    if not text:
        return 0
    # 中文字符占比启发式：若非 ASCII 字符 >30% 当作中文为主
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii / max(len(text), 1) > 0.3:
        return max(1, int(len(text) / 1.5))
    return max(1, int(len(text) / 4))
