"""Handle inline button CAPTCHA: click the verify button."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


VERIFY_BUTTON_KEYWORDS = ["human", "verify", "我不是机器人", "通过", "i am", "yes", "确认"]


async def solve_inline_button(*, telethon_client, message, dry_run: bool = False) -> dict:
    """
    message: telethon Message with reply_markup (inline keyboard).
    返回: {"success": bool, "clicked_button": str | None, "error": str | None}
    """
    if not message.reply_markup:
        return {"success": False, "clicked_button": None, "error": "no_keyboard"}

    target_button = None
    for row in message.buttons or []:
        for btn in row:
            btn_text = (btn.text or "").lower()
            if any(kw.lower() in btn_text for kw in VERIFY_BUTTON_KEYWORDS):
                target_button = btn
                break
        if target_button:
            break

    if not target_button:
        return {"success": False, "clicked_button": None, "error": "no_verify_button_found"}

    if dry_run:
        return {"success": True, "clicked_button": target_button.text, "error": None}

    try:
        await target_button.click()
        return {"success": True, "clicked_button": target_button.text, "error": None}
    except Exception as e:
        logger.exception("inline button click failed")
        return {"success": False, "clicked_button": target_button.text, "error": str(e)}
