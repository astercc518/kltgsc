"""Handle text Q&A captcha: LLM generates answer using customer-provided context."""
import logging
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def solve_text_qa(
    *,
    client=None,
    chat_id: int,
    question: str,
    customer_join_template: Optional[str],
    dry_run: bool = False,
    telethon_client=None,
) -> dict:
    """
    Generate a short answer via LLM and send it as a group message.

    `client` is a pyrogram Client (send_message API is the same shape as the
    test mocks). `telethon_client` is accepted as alias for backward compat.

    Returns: {"success": bool, "answer": str | None, "error": str | None}
    """
    real_client = client if client is not None else telethon_client

    if not question or not question.strip():
        return {"success": False, "answer": None, "error": "empty_question"}

    if dry_run:
        return {"success": True, "answer": "[dry_run placeholder]", "error": None}

    template_block = customer_join_template or "我是行业内朋友推荐知道的"
    prompt = f"""你是一个加入 TG 群的新成员, 群里 bot 问了一个验证问题. 简短回答 (不超 30 字), 用日常口语:

背景 (你为什么加这群): {template_block}

问题: {question}

回答:
"""

    with Session(engine) as session:
        svc = LLMService(session)
        answer = await svc.generate(prompt, source="captcha_text_qa")

    if not answer or len(answer) > 100:
        return {"success": False, "answer": answer, "error": "bad_llm_response"}

    if real_client is None:
        return {"success": False, "answer": answer, "error": "no_client"}

    try:
        await real_client.send_message(chat_id, answer)
        return {"success": True, "answer": answer, "error": None}
    except Exception as e:
        logger.exception("text_qa send failed")
        return {"success": False, "answer": answer, "error": str(e)}
