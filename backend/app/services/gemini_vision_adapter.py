"""
gemini_vision_adapter — 调 Gemini Pro Vision 识别 CAPTCHA 图片.

Two surfaces:
- analyze_captcha_image() : free-form description (Phase 8 contract). Used by
  the vision-only handler which marks the attempt 'manual_review_needed'.
- analyze_captcha_button_choice() : Phase 12 hybrid. When the captcha message
  has BOTH a photo AND inline buttons, ask Gemini to pick which button
  answers the question in the image. Returns the picked button text or None.
"""
import base64
import json
import logging
import os
import re
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


GEMINI_VISION_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)


def _detect_mime_type(image_bytes: bytes) -> str:
    """Detect MIME type from image header bytes."""
    if image_bytes[:2] == b'\xff\xd8':
        return "image/jpeg"
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if image_bytes[:6] in (b'GIF87a', b'GIF89a'):
        return "image/gif"
    return "image/png"  # safe default


async def analyze_captcha_image(
    *, image_bytes: bytes, prompt_hint: str = "",
) -> Optional[str]:
    """
    image_bytes: raw 图片 bytes (PNG/JPEG)
    prompt_hint: 群 bot 的提示文字 e.g. "请选择所有汽车"
    Returns: LLM 的描述 + 建议 (e.g. "图片显示 6 个格子, 第 1,3,5 格是汽车")
    或 None on failure (missing key, API error, empty response).
    """
    key = os.getenv("GEMINI_VISION_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_VISION_API_KEY not set; vision captcha disabled")
        return None

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = _detect_mime_type(image_bytes)
    body = {
        "contents": [{
            "parts": [
                {"text": f"分析这张 CAPTCHA 图片. {prompt_hint}\n描述图片内容并建议如何回答."},
                {"inline_data": {"mime_type": mime_type, "data": b64}},
            ],
        }],
        "generationConfig": {"maxOutputTokens": 200},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GEMINI_VISION_URL}?key={key}", json=body,
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("Gemini Vision call failed")
        return None

    candidates = data.get("candidates", [])
    if not candidates:
        return None
    content = candidates[0].get("content", {}).get("parts", [])
    if not content:
        return None
    return content[0].get("text", "").strip() or None


async def analyze_captcha_button_choice(
    *,
    image_bytes: bytes,
    button_texts: List[str],
    prompt_hint: str = "",
) -> Optional[str]:
    """
    Phase 12 hybrid path.

    Given a captcha image and a list of inline button labels, ask Gemini Vision
    to look at the image, read any question/instruction in it, and pick which
    button text is the correct answer. Returns the exact button text (so the
    caller can drive Message.click(text)), or None if Gemini can't decide /
    the API is unavailable / the response doesn't match any provided label.

    The model is asked to reply JSON: {"button": "<label>"} so the output is
    unambiguous; if it returns prose instead we fall back to a tolerant
    substring scan against the candidate labels.
    """
    key = os.getenv("GEMINI_VISION_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning(
            "GEMINI_VISION_API_KEY not set; vision button-choice disabled",
        )
        return None
    if not button_texts:
        return None

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = _detect_mime_type(image_bytes)

    labels_block = "\n".join(f"- {t}" for t in button_texts)
    prompt = (
        "You are solving a Telegram CAPTCHA. The image contains a question or "
        "instruction. Pick the SINGLE inline button below that correctly "
        "answers it. If multiple buttons could be valid, pick the most "
        "specific one. Respond ONLY with strict JSON: "
        '{"button": "<exact button label>"}.\n\n'
        f"Buttons:\n{labels_block}\n\n"
        f"Bot hint (if any): {prompt_hint or '(none)'}"
    )

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": b64}},
            ],
        }],
        "generationConfig": {
            "maxOutputTokens": 80,
            "temperature": 0.0,  # deterministic — we want one answer
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GEMINI_VISION_URL}?key={key}", json=body,
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("Gemini Vision button-choice call failed")
        return None

    candidates = data.get("candidates", [])
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return None
    raw = (parts[0].get("text") or "").strip()
    if not raw:
        return None

    chosen = _parse_button_choice(raw, button_texts)
    if chosen is None:
        logger.info(
            "vision button-choice: model response did not match any button: %r",
            raw[:200],
        )
    return chosen


def _parse_button_choice(
    raw: str, button_texts: List[str],
) -> Optional[str]:
    """
    Extract the button label from a model response. Tries strict JSON first
    (the prompt asks for it); falls back to exact match, then case-insensitive
    substring scan against the candidate labels.
    """
    # 1. strict JSON ({"button": "..."}) — may be wrapped in code fences.
    cleaned = raw
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    try:
        parsed = json.loads(cleaned)
        candidate = parsed.get("button") if isinstance(parsed, dict) else None
        if isinstance(candidate, str):
            stripped = candidate.strip()
            for label in button_texts:
                if label == stripped:
                    return label
            # case-insensitive exact match if the model casing drifted
            for label in button_texts:
                if label.lower() == stripped.lower():
                    return label
    except (json.JSONDecodeError, AttributeError):
        pass

    # 2. fall back: scan for a label that appears as a standalone token in
    #    the response. Word-boundary regex prevents single-char labels like
    #    "C" from incorrectly matching inside words like "Cannot".
    for label in button_texts:
        if not label:
            continue
        pattern = r"(?<!\w)" + re.escape(label) + r"(?!\w)"
        if re.search(pattern, raw):
            return label

    # 3. case-insensitive standalone-token scan as a last resort.
    for label in button_texts:
        if not label:
            continue
        pattern = r"(?<!\w)" + re.escape(label) + r"(?!\w)"
        if re.search(pattern, raw, flags=re.IGNORECASE):
            return label

    return None
