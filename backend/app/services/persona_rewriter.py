"""
persona_rewriter — 纯字符串变换, 按 persona 调语气/口头禅/标点。

无 LLM. 确定性 (seed 可控). 零成本可测试。

支持的 speaking_style:
  formal: 不变
  casual: 句末偶尔加 哈/咯/嗯, 30% 加口头禅, 标点拟人化
  techy: 1-2 个术语替换 (客户→用户, 方案→打法)
  northeastern_dialect: 搞→整, 应该→得
  cantonese_flavor: 是→系, 句末加 啦
"""
import random
import re
from typing import Optional

MAX_REPLY_LENGTH = 80

CASUAL_PARTICLES = ["哈", "咯", "嗯"]

TECHY_REPLACEMENTS = [
    ("客户", "用户"),
    ("方案", "打法"),
]

NORTHEASTERN_REPLACEMENTS = [
    ("搞", "整"),
    ("应该", "得"),
]

CANTONESE_REPLACEMENTS = [
    ("是", "系"),
]


def _truncate_at_sentence_end(text: str, max_length: int) -> str:
    """超长 → 截到最近句末标点"""
    if len(text) <= max_length:
        return text
    candidate = text[:max_length]
    # 倒数找句末标点
    for i in range(len(candidate) - 1, -1, -1):
        if candidate[i] in "。？！.?!":
            return candidate[:i + 1]
    return candidate.rstrip(",，、 ")


def _maybe_append_casual_particle(text: str, rng: random.Random) -> str:
    """30% 概率句末加 casual particle (在末标点前)"""
    if rng.random() > 0.3:
        return text
    if not text:
        return text
    particle = rng.choice(CASUAL_PARTICLES)
    # 末尾有句号/感叹号: 插在它前面
    if text[-1] in "。？！.?!":
        return text[:-1] + particle + text[-1]
    return text + particle


def _maybe_insert_catchphrase(
    text: str, catchphrases: list[str], rng: random.Random,
) -> str:
    if not catchphrases:
        return text
    if rng.random() > 0.3:
        return text
    cp = rng.choice(catchphrases)
    # 插入位置: 第一个逗号后或开头
    comma_match = re.search(r"[,，]", text)
    if comma_match:
        idx = comma_match.end()
        return text[:idx] + cp + text[idx:]
    return cp + " " + text


def _apply_word_replacements(text: str, pairs: list[tuple[str, str]]) -> str:
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def apply_persona(
    text: Optional[str], persona: dict, seed: Optional[int] = None,
) -> Optional[str]:
    """主入口。"""
    if text is None or text == "":
        return text

    rng = random.Random(seed)
    style = (persona or {}).get("speaking_style", "casual")
    catchphrases = (persona or {}).get("catchphrases", []) or []

    out = text

    if style == "formal":
        pass  # 不变
    elif style == "casual":
        out = _maybe_insert_catchphrase(out, catchphrases, rng)
        out = _maybe_append_casual_particle(out, rng)
    elif style == "techy":
        out = _apply_word_replacements(out, TECHY_REPLACEMENTS)
        out = _maybe_insert_catchphrase(out, catchphrases, rng)
    elif style == "northeastern_dialect":
        out = _apply_word_replacements(out, NORTHEASTERN_REPLACEMENTS)
        out = _maybe_insert_catchphrase(out, catchphrases, rng)
    elif style == "cantonese_flavor":
        out = _apply_word_replacements(out, CANTONESE_REPLACEMENTS)
        # 句末加 啦
        if out and out[-1] not in "。？！.?!":
            out = out + "啦"
        out = _maybe_insert_catchphrase(out, catchphrases, rng)
    else:
        out = _maybe_insert_catchphrase(out, catchphrases, rng)

    # 二次长度校验
    out = _truncate_at_sentence_end(out, MAX_REPLY_LENGTH)
    return out
