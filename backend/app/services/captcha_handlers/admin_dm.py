"""Admin DM handler: send customer-template intro DM to group admin."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def solve_admin_dm(
    *,
    client=None,
    admin_user_id: int,
    customer_intro_template: Optional[str],
    dry_run: bool = False,
    telethon_client=None,
) -> dict:
    """
    Send a customer-provided intro template as a DM to the group admin.

    `client` is a pyrogram Client. `telethon_client` is accepted as alias for
    backward compat with existing unit tests.

    Returns: {"success": bool, "answer": str | None, "error": str | None}
    """
    real_client = client if client is not None else telethon_client

    if not customer_intro_template:
        return {"success": False, "answer": None, "error": "no_template_set"}

    if dry_run:
        return {"success": True, "answer": customer_intro_template, "error": None}

    if real_client is None:
        return {"success": False, "answer": None, "error": "no_client"}

    try:
        await real_client.send_message(admin_user_id, customer_intro_template)
        return {"success": True, "answer": customer_intro_template, "error": None}
    except Exception as e:
        logger.exception("admin_dm send failed")
        return {"success": False, "answer": None, "error": str(e)}
