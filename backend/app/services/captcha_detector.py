"""
captcha_detector — 识别加群后遇到的 CAPTCHA 类型.

调用时机: 加群后等 10s 拉前 5 条新消息.
返回: 'inline_button' | 'text_qa' | 'vision' | 'admin_dm' | 'no_captcha' | 'unknown'
"""
import logging

logger = logging.getLogger(__name__)


INLINE_KEYWORDS = ["human", "verify", "我不是", "robot", "captcha", "点击", "tap", "按一下"]
QA_INDICATORS = ["?", "？"]


def detect_captcha_type(
    *, recent_messages: list[dict], admin_dms_after_join: list[dict],
) -> dict:
    """
    recent_messages: [{"text": str, "buttons": [str], "has_photo": bool, "from_bot": bool}, ...]
    admin_dms_after_join: [{"text": str, "from_user_id": int}, ...]
    Returns: {"type": str, "evidence": {...}}
    """
    if not recent_messages and not admin_dms_after_join:
        return {"type": "no_captcha", "evidence": {}}

    # Check inline button
    for msg in recent_messages:
        if msg.get("buttons"):
            text = (msg.get("text") or "").lower()
            buttons_text = " ".join(msg.get("buttons", [])).lower()
            combined = text + " " + buttons_text
            if any(kw in combined for kw in INLINE_KEYWORDS):
                return {
                    "type": "inline_button",
                    "evidence": {"message": msg},
                }

    # Check vision (image + bot)
    for msg in recent_messages:
        if msg.get("has_photo") and msg.get("from_bot"):
            return {
                "type": "vision",
                "evidence": {"message": msg},
            }

    # Check text Q&A
    for msg in recent_messages:
        text = msg.get("text") or ""
        if msg.get("from_bot") and any(q in text for q in QA_INDICATORS) and len(text) < 100:
            return {
                "type": "text_qa",
                "evidence": {"question": text, "message": msg},
            }

    # Admin DM check
    if admin_dms_after_join:
        return {
            "type": "admin_dm",
            "evidence": {"dms": admin_dms_after_join},
        }

    return {"type": "unknown", "evidence": {"messages": recent_messages}}
