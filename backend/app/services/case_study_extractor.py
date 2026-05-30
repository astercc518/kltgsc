"""
case_study_extractor — 从客户主号聊天历史中 LLM 抽取成交案例。

复用 qa_extractor 思路, 但目标是"成交事件"而不是"Q&A 对":
  - 输入: customer.id, 主号 chat_history 表最近 N 条对话
  - 处理: 让 LLM 识别"完成的成交事件", 输出结构化案例数组
  - 输出: [{industry, deal_size, period, problem, solution, outcome, tags}, ...]
  - 不直接写库. 调用方 (admin endpoint) 决定是否 confirm 入库。

Note: ChatHistory rows are linked to Account (via account_id), and Account has
customer_id. We join through Account to filter by customer.
ChatHistory uses `content` (not `text`) and `role` (not `sender_id`).
"""
import json
import logging
from typing import Optional

from app.models.chat_history import ChatHistory
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


def _fetch_chat_history(*, session, customer_id: int, max_history: int = 100) -> list:
    """取该客户主号最近 max_history 条聊天历史。

    ChatHistory.account_id → Account.id → Account.customer_id。
    按 created_at desc 取最近 N 条, 再 reverse 还原成时间顺序供 LLM 阅读。
    """
    from sqlmodel import select
    from app.models.account import Account

    # Join ChatHistory → Account on account_id, filter by customer_id
    stmt = (
        select(ChatHistory)
        .join(Account, ChatHistory.account_id == Account.id)
        .where(Account.customer_id == customer_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(max_history)
    )
    rows = list(session.exec(stmt).all())
    # 还原成时间顺序 (asc)
    rows.reverse()
    return rows


async def _llm_extract(*, session, history: list) -> Optional[str]:
    """LLM 分析对话, 输出 JSON 数组字符串。"""
    if not history:
        return None
    dialogue = "\n".join(
        f"{getattr(h, 'role', '?')}: {getattr(h, 'content', getattr(h, 'text', ''))}"
        for h in history
    )
    prompt = f"""从下面这段聊天对话里找出所有"已完成成交"的案例 (双方达成合作, 有具体金额或规模, 客户表示完成 / 满意)。

聊天:
{dialogue}

为每个识别出的成交输出一个对象, 格式如下 (JSON 数组, 不要 markdown 包装):
[
  {{
    "industry": 一句话行业 (如 "OTC" / "教培" / "SaaS") 或 "",
    "deal_size": 成交规模 (如 "100k USDT" / "30 万人民币") 或 "",
    "period": 成交周期 (如 "3 天" / "1 周") 或 "",
    "problem": 客户的问题需求,
    "solution": 我方提出的方案,
    "outcome": 实际效果 (含数字),
    "tags": [标签字符串数组]
  }},
  ...
]

如果整段聊天没有任何完成成交, 返回空数组 [].
"""
    svc = LLMService(session)
    return await svc.generate(prompt, source="case_extract")


async def extract_cases_for_customer(
    *, session, customer_id: int, max_history: int = 100,
) -> list[dict]:
    """
    返回 LLM 抽取的案例候选列表 (尚未入库)。调用方决定 confirm / discard。
    失败 / 无数据 → 空列表 (调用方不 raise)。
    """
    history = _fetch_chat_history(
        session=session, customer_id=customer_id, max_history=max_history,
    )
    if not history:
        return []

    raw = await _llm_extract(session=session, history=history)
    if not raw:
        return []

    # 容忍 markdown 包装
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = cleaned.strip("`").strip()

    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("case extract: bad JSON: %r", raw[:200])
        return []

    if not isinstance(parsed, list):
        return []

    # 过滤掉 problem/solution/outcome 任一为空的
    result = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if not (item.get("problem") and item.get("solution") and item.get("outcome")):
            continue
        result.append({
            "industry": item.get("industry", "") or "",
            "deal_size": item.get("deal_size", "") or "",
            "period": item.get("period", "") or "",
            "problem": item["problem"], "solution": item["solution"],
            "outcome": item["outcome"],
            "tags": item.get("tags", []) or [],
        })
    return result
