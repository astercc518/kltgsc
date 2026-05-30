"""Handle text Q&A captcha: LLM generates answer using customer-provided context."""
import logging
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def solve_text_qa(
    *,
    telethon_client,
    chat_id: int,
    question: str,
    customer_join_template: Optional[str],
    dry_run: bool = False,
) -> dict:
    """
    customer_join_template: 客户预填的"我们如何知道这个群" 上下文.
    返回: {"success": bool, "answer": str | None, "error": str | None}
    """
    if not question or not question.strip():
        return {"success": False, "answer": None, "error": "empty_question"}

    if dry_run:
        # Skip LLM call in dry_run; return placeholder
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

    try:
        await telethon_client.send_message(chat_id, answer)
        return {"success": True, "answer": answer, "error": None}
    except Exception as e:
        logger.exception("text_qa send failed")
        return {"success": False, "answer": answer, "error": str(e)}
