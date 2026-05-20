"""
LLM/Embedding 调用的 token & 成本上报。

设计原则：写失败不阻塞主流程，只 warn；用独立 short-lived session 避免污染调用方。
"""
import logging
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.models.llm_usage import LLMUsage
from app.services.pricing import calc_cost_usd

logger = logging.getLogger(__name__)


def record_usage(
    provider: str,
    model: str,
    source: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    account_id: Optional[int] = None,
    persona_id: Optional[int] = None,
    chat_id: Optional[str] = None,
    cost_usd: Optional[float] = None,
) -> None:
    """
    同步写一条 LLMUsage。每次都开独立 session，避免和调用方共享 session 引发事务冲突。

    cost_usd 不传时按 PRICING_USD_PER_1M 自动计算。
    """
    try:
        if cost_usd is None:
            cost_usd = calc_cost_usd(model, input_tokens, output_tokens)
        with Session(engine) as session:
            row = LLMUsage(
                provider=provider,
                model=model,
                source=source,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                account_id=account_id,
                persona_id=persona_id,
                chat_id=str(chat_id) if chat_id is not None else None,
            )
            session.add(row)
            session.commit()
    except Exception as e:
        logger.warning(f"record_usage failed (source={source}, model={model}): {e}")
