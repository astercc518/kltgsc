"""
vision_button_hybrid — Phase 12 hybrid captcha handler.

Triggered when the bot message has BOTH a photo and inline buttons:
  1. Download the photo via the existing vision-handler helper.
  2. Ask Gemini Vision which button label answers the question in the image.
  3. Drive solve_inline_button(preferred_text=...) to click that button.

If any step fails (vision unavailable, model can't decide, button missing),
the handler degrades to keyword-scan inline_button. If THAT also fails the
attempt is reported as failed and orchestrator's retry / final-fail logic
takes over.
"""
import logging
from typing import Optional

from app.services.captcha_handlers.inline_button import (
    list_button_texts,
    solve_inline_button,
)
from app.services.captcha_handlers.vision import _download_to_bytes
from app.services.gemini_vision_adapter import analyze_captcha_button_choice

logger = logging.getLogger(__name__)


async def solve_vision_button_hybrid(
    *,
    client=None,
    message,
    dry_run: bool = False,
    telethon_client=None,
) -> dict:
    """
    Returns: {"success": bool, "clicked_button": str | None,
              "picked_via": str, "error": str | None}

    picked_via ∈ {"vision", "keyword_fallback"}
    """
    real_client = client if client is not None else telethon_client

    button_texts = list_button_texts(message)
    if not button_texts:
        return {
            "success": False,
            "clicked_button": None,
            "picked_via": "vision",
            "error": "no_buttons_on_message",
        }

    if not getattr(message, "photo", None):
        # No photo → just defer to the keyword-scan handler (no vision call).
        fallback = await solve_inline_button(
            client=real_client, message=message, dry_run=dry_run,
        )
        fallback["picked_via"] = "keyword_fallback"
        return fallback

    preferred: Optional[str] = None
    if not dry_run:
        image_bytes = await _download_to_bytes(real_client, message)
        if image_bytes is None:
            logger.warning("vision_button_hybrid: image download failed")
        else:
            try:
                prompt_hint = (
                    getattr(message, "text", "")
                    or getattr(message, "caption", "")
                    or ""
                )
                preferred = await analyze_captcha_button_choice(
                    image_bytes=image_bytes,
                    button_texts=button_texts,
                    prompt_hint=prompt_hint,
                )
            except Exception as exc:
                logger.warning(
                    "vision_button_hybrid: gemini call raised %s", exc,
                )

    if preferred:
        result = await solve_inline_button(
            client=real_client,
            message=message,
            dry_run=dry_run,
            preferred_text=preferred,
        )
        result["picked_via"] = "vision"
        return result

    # Vision couldn't decide — fall back to keyword scan.
    fallback = await solve_inline_button(
        client=real_client, message=message, dry_run=dry_run,
    )
    fallback["picked_via"] = "keyword_fallback"
    return fallback
