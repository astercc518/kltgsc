"""
gemini_vision_adapter — 调 Gemini Pro Vision 识别 CAPTCHA 图片.
Returns: 文本描述图片内容 + 建议的 click action.
"""
import base64
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


GEMINI_VISION_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)


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
    body = {
        "contents": [{
            "parts": [
                {"text": f"分析这张 CAPTCHA 图片. {prompt_hint}\n描述图片内容并建议如何回答."},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
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
