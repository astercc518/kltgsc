"""Vision CAPTCHA handler: download image → Gemini Vision → analysis for manual review."""
import logging

from app.services.gemini_vision_adapter import analyze_captcha_image

logger = logging.getLogger(__name__)


async def solve_vision(
    *, telethon_client, message, dry_run: bool = False,
) -> dict:
    """
    Download photo from message, analyze via Gemini Vision.

    Phase 8 simplification: vision 仅做 analysis, 不自动 click.
    返回: {"success": bool, "analysis": str | None, "action_taken": str | None, "error": str | None}
    """
    if not message.photo:
        return {"success": False, "analysis": None, "action_taken": None, "error": "no_photo"}

    try:
        image_bytes = await telethon_client.download_media(message, file=bytes)
    except Exception as e:
        return {
            "success": False,
            "analysis": None,
            "action_taken": None,
            "error": f"download_failed: {e}",
        }

    prompt_hint = message.text or ""
    analysis = await analyze_captcha_image(image_bytes=image_bytes, prompt_hint=prompt_hint)
    if not analysis:
        return {
            "success": False,
            "analysis": None,
            "action_taken": None,
            "error": "vision_api_failed",
        }

    # Phase 8: vision 仅分析 + 标记 manual review.
    # 如果 CAPTCHA 图片配有 inline button，由 inline_button handler 接管 click.
    # dry_run 时仅返回 analysis，不影响 action_taken 语义.
    if dry_run:
        return {"success": True, "analysis": analysis, "action_taken": None, "error": None}

    return {
        "success": False,  # Phase 8: vision 仅分析, 需人工接管
        "analysis": analysis,
        "action_taken": "manual_review_needed",
        "error": None,
    }
