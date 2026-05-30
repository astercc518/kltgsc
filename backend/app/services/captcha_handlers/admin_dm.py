"""Admin DM handler: send customer-template intro DM to group admin."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def solve_admin_dm(
    *,
    telethon_client,
    admin_user_id: int,
    customer_intro_template: Optional[str],
    dry_run: bool = False,
) -> dict:
    """
    Send a customer-provided intro template as a DM to the group admin.

    customer_intro_template: 客户预填的"申请加群"模板.
    e.g. "你好, 看到xx推荐的, 想加群学习交流."
    返回: {"success": bool, "answer": str | None, "error": str | None}
    """
    if not customer_intro_template:
        return {"success": False, "answer": None, "error": "no_template_set"}

    if dry_run:
        return {"success": True, "answer": customer_intro_template, "error": None}

    try:
        await telethon_client.send_message(admin_user_id, customer_intro_template)
        return {"success": True, "answer": customer_intro_template, "error": None}
    except Exception as e:
        logger.exception("admin_dm send failed")
        return {"success": False, "answer": None, "error": str(e)}
