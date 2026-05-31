"""Vision CAPTCHA handler: download image → Gemini Vision → analysis for manual review."""
import logging

from app.services.gemini_vision_adapter import analyze_captcha_image

logger = logging.getLogger(__name__)


async def _download_to_bytes(client, message) -> bytes | None:
    """
    Download a photo to memory bytes.

    Pyrogram path: `client.download_media(message, in_memory=True)` returns a
    BinaryIO with `.getvalue()` available. We also tolerate the test-time
    mock signature `client.download_media(message, file=bytes)` which returns
    bytes directly.
    """
    if client is None:
        return None
    try:
        try:
            buf = await client.download_media(message, in_memory=True)
        except TypeError:
            buf = await client.download_media(message, file=bytes)
    except Exception as exc:
        logger.warning("vision download_media failed: %s", exc)
        return None

    if buf is None:
        return None
    if isinstance(buf, (bytes, bytearray)):
        return bytes(buf)
    getvalue = getattr(buf, "getvalue", None)
    if callable(getvalue):
        try:
            return getvalue()
        except Exception:
            return None
    return None


async def solve_vision(
    *,
    client=None,
    message,
    dry_run: bool = False,
    telethon_client=None,
) -> dict:
    """
    Download photo from message, analyse via Gemini Vision.

    Phase 8 contract: vision is analysis-only; never auto-clicks.

    Returns: {"success": bool, "analysis": str | None,
              "action_taken": str | None, "error": str | None}
    """
    real_client = client if client is not None else telethon_client

    if not getattr(message, "photo", None):
        return {"success": False, "analysis": None, "action_taken": None, "error": "no_photo"}

    image_bytes = await _download_to_bytes(real_client, message)
    if image_bytes is None:
        return {
            "success": False,
            "analysis": None,
            "action_taken": None,
            "error": "download_failed",
        }

    prompt_hint = getattr(message, "text", "") or getattr(message, "caption", "") or ""
    analysis = await analyze_captcha_image(image_bytes=image_bytes, prompt_hint=prompt_hint)
    if not analysis:
        return {
            "success": False,
            "analysis": None,
            "action_taken": None,
            "error": "vision_api_failed",
        }

    if dry_run:
        return {"success": True, "analysis": analysis, "action_taken": None, "error": None}

    # Phase 8 contract: vision is analysis-only, marks manual review needed.
    return {
        "success": False,
        "analysis": analysis,
        "action_taken": "manual_review_needed",
        "error": None,
    }
