"""
Q&A 抽取服务
- 输入：一段连续的群消息
- 输出：业务相关的问答对（用于 RAG）
"""
import json
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

from sqlmodel import Session

from app.services.llm import LLMService

logger = logging.getLogger(__name__)


QA_EXTRACTION_SYSTEM = """你是 Telegram 出海/灰产社群知识抽取员。这些群的特点是大量"号商/数据商/服务商打广告"，你要把每条**有可识别内容的广告/服务/对话**全部转成 Q&A 入库。

宁可多抽 10 条无关的，也不要漏抽 1 条有用的。**没有可抽内容时才返回空数组**。

【必抽内容】
1. **号商/数据商广告**：每个独立服务商 = 1 条 Q&A
   - Q 例：「谁有 Facebook 老白号？」/「TRX 能量哪里买便宜？」/「做不了印尼短信怎么办？」
   - A：把广告原文核心信息保留：商家名 + 主营 + 价格(若有) + 联系方式(@xxx / t.me/xxx)

2. **接单/出货短消息**："拍商家马80一单"、"五原✈肥鸡号"、"你有手机給小时一千"、"谁有U,大量收 @jiufu178"
   - 这种碎片消息**一条一抽**：Q="如何接 XX 业务/在哪找 XX 资源"，A=原话+联系方式

3. **服务报价**：任何带价格、汇率、佣金、套餐的消息

4. **群规/管理通告**：协议号管理、广告政策、风控规则

5. **真实问答对话**：群友 A 问 B 答 → 标准 Q&A

6. **私聊**（重要！）：私聊里几乎所有有内容的消息都抽，因为是真实业务沟通

【跳过的内容】（仅这些）
- 纯表情/贴纸/图片名（"[图片]"）
- 单字符回复（"好"、"嗯"、"在"、"哈"）
- 群成员加入/退出系统消息

【输出要求】
- 联系方式 (@xxx / t.me/xxx / 电话号 / 网址) 必须保留在 A 里
- 价格/数字/产品名原样保留
- Q 用群友会问的口吻：「谁有...」「...怎么搞」「...多少钱」「在哪找...」
- 同一商家重复广告，**保留一条即可**（去重）
- topic 用 5 字内中文短语：号商资源/短信服务/数据销售/TRX能量/博彩平台/群规通告/技术问答/接单需求/价格咨询...
- tags 2-5 个

只返回 JSON 数组，不要任何前后文字、不要 ```json fences。
格式：
[{"question":"...","answer":"...","topic":"...","tags":["...","..."]}]"""


def _format_messages_for_prompt(messages: List[Dict]) -> str:
    """把 GroupMessage 列表格式化成对话文本"""
    lines = []
    for m in messages:
        ts = m["date"].strftime("%m-%d %H:%M") if m.get("date") else "??-?? ??:??"
        sender = m.get("sender_name") or m.get("sender_username") or f"#{m.get('sender_id') or '?'}"
        content = (m.get("content") or "").replace("\n", " ")[:500]
        if m.get("reply_to"):
            lines.append(f"[{ts}] {sender} ↩#{m['reply_to']}: {content}")
        else:
            lines.append(f"[{ts}] {sender}: {content}")
    return "\n".join(lines)


def _parse_json_response(text: str) -> List[Dict]:
    """从 LLM 输出里提取 JSON 数组（容错处理 markdown fences）"""
    if not text:
        return []
    text = text.strip()
    # 去除 ```json ... ``` 包裹
    fence = re.match(r"^```(?:json)?\s*\n?(.+?)\n?```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "qa" in data:
            return data["qa"] if isinstance(data["qa"], list) else []
        return []
    except json.JSONDecodeError:
        # 尝试从字符串中找第一个 [ 到最后一个 ]
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                return []
        return []


async def extract_qa_from_window(
    llm: LLMService,
    chat_title: str,
    chat_type: str,
    messages: List[Dict],
) -> List[Dict]:
    """
    对一段消息窗口调用 LLM 抽取 Q&A。
    messages: [{date, sender_name, sender_username, sender_id, content, reply_to}]
    返回: [{question, answer, topic, tags: []}]
    """
    if not messages or not llm.is_configured():
        return []

    conversation = _format_messages_for_prompt(messages)
    prompt = f"群名：{chat_title}（{chat_type}）\n\n聊天记录：\n{conversation}"

    raw = await llm.get_response(prompt=prompt, system_prompt=QA_EXTRACTION_SYSTEM)
    if not raw:
        return []

    qa_list = _parse_json_response(raw)
    # 校验
    cleaned = []
    for qa in qa_list:
        if not isinstance(qa, dict):
            continue
        q = (qa.get("question") or "").strip()
        a = (qa.get("answer") or "").strip()
        if not q or not a:
            continue
        cleaned.append({
            "question": q[:1000],
            "answer": a[:2000],
            "topic": (qa.get("topic") or "其他")[:50],
            "tags": qa.get("tags") if isinstance(qa.get("tags"), list) else [],
        })
    return cleaned
