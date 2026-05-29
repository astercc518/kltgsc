"""
chitchat_scheduler — Celery beat task 每 5min 触发。

对每个 worker account × 每个常驻群:
  1. 当天 chitchat_log 计数 / 剩余配额
  2. 互斥窗口: 5min 内若有 business reply → 跳
  3. 概率算法: remaining_quota / hours_left / 12 (每小时 12 次 tick)
  4. 随机选话题 → 检查不命中本群 monitor.keyword_filters.include
  5. LLM 演绎话题 prompt_template → 文本
  6. 反幻觉过滤 (轻量)
  7. dispatch_chitchat 入队
"""
import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.account import Account
from app.models.chitchat import ChitchatPool, ChitchatLog
from app.services.worker_persona_service import get_persona_for_account
from app.services.chitchat_dispatch import dispatch_chitchat
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


def _decide_to_chitchat(
    *, persona: dict, sent_today_count: int,
    hours_left_today: float, recent_business_reply: bool,
    seed: Optional[int] = None,
) -> dict:
    """是否在本 tick 触发闲聊。"""
    quota = persona.get("daily_chitchat_quota", 0)
    remaining = max(0, quota - sent_today_count)
    if remaining <= 0:
        return {"fire": False, "reason": "quota_exhausted"}
    if recent_business_reply:
        return {"fire": False, "reason": "business_reply_within_5min"}

    hours = max(0.5, hours_left_today)
    # 每小时 12 次 tick (5min 一次); 全天均匀分布概率
    fire_prob = min(0.5, remaining / hours / 12)
    rng = random.Random(seed)
    if rng.random() > fire_prob:
        return {"fire": False, "reason": "prob_miss"}
    return {"fire": True, "reason": None}


def _list_active_worker_accounts() -> list:
    """所有 active worker 账号 (Phase 3a 直接全量, 大客户量后续可分批)。"""
    with Session(engine) as session:
        rows = session.exec(
            select(Account).where(
                Account.role == "worker",
                Account.status == "active",
            )
        ).all()
        return list(rows)


def _list_joined_chats_for_account(account) -> list[tuple[int, list[str]]]:
    """
    返回 [(chat_id, [include_keywords_for_this_chat]), ...]

    根据 monitor 配置反查: 该 account 监听的 chat_id 及对应 monitor
    的 keyword_filters.include 列表 (用于避免闲聊命中自家关键词)。
    """
    # Phase 3a 简化: 复用 listener 的 monitor 表查询。
    # 详细实现以 listener_service 现有路径为准, 此处给桩。
    from app.models.keyword_monitor import KeywordMonitor
    with Session(engine) as session:
        monitors = session.exec(
            select(KeywordMonitor).where(
                KeywordMonitor.customer_id == account.customer_id,
                KeywordMonitor.is_active == True,
            )
        ).all()
        chats = []
        for m in monitors:
            targets = (m.target_groups or "").split(",")
            include_kws = (m.keyword_filters or {}).get("include", []) if m.keyword_filters else (
                [m.keyword] if m.keyword else []
            )
            for raw_chat in targets:
                raw_chat = raw_chat.strip()
                try:
                    chat_id = int(raw_chat)
                except ValueError:
                    continue
                chats.append((chat_id, include_kws))
        return chats


def _chitchat_log_count_today(*, account_id: int, chat_id: int) -> int:
    today = datetime.now(timezone.utc).date()
    with Session(engine) as session:
        from sqlalchemy import func
        cnt = session.exec(
            select(func.count(ChitchatLog.id)).where(
                ChitchatLog.account_id == account_id,
                ChitchatLog.chat_id == chat_id,
                # func.timezone enforces UTC interpretation regardless of PG session tz
                # sent_at is TIMESTAMP WITHOUT TIME ZONE (UTC-naive writes), so this is
                # a no-op semantically but guards against non-UTC session_timezone configs
                func.date(func.timezone("UTC", ChitchatLog.sent_at)) == today,
            )
        ).first()
        return int(cnt or 0)


def _has_recent_business_reply(*, account_id: int, chat_id: int, minutes: int = 5) -> bool:
    """5min 内有 pending_replies.status='sent' by this account in this chat."""
    from app.models.pending_reply import PendingReply, PendingReplyStatus
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    with Session(engine) as session:
        row = session.exec(
            select(PendingReply).where(
                PendingReply.responder_account_id == account_id,
                PendingReply.chat_id == chat_id,
                PendingReply.status == PendingReplyStatus.SENT.value,
                PendingReply.sent_at >= cutoff,
            ).limit(1)
        ).first()
        return row is not None


def _pick_random_chitchat_topic() -> Optional[ChitchatPool]:
    """随机选一条 active 话题 (全局 + 客户自定义都行)。"""
    with Session(engine) as session:
        topics = session.exec(
            select(ChitchatPool).where(ChitchatPool.active == True)
        ).all()
        topics = list(topics)
        if not topics:
            return None
        return random.choice(topics)


def _topic_hits_monitor_keywords(topic: ChitchatPool, include_kws: list[str]) -> bool:
    if not include_kws:
        return False
    template_lower = (topic.prompt_template or "").lower()
    return any(kw.lower() in template_lower for kw in include_kws)


async def _llm_render_chitchat(template: str, persona: dict) -> Optional[str]:
    """让 LLM 把模板演绎成具体文本。"""
    style = persona.get("speaking_style", "casual")
    prompt = f"""把下面这个 TG 群闲聊模板演绎成一句自然口语 (不超 40 字, 不要 emoji), 风格 {style}:

模板: {template}
"""
    with Session(engine) as session:
        svc = LLMService(session)
        return await svc.generate(prompt, source="chitchat_render")


def _hours_left_today(persona: dict) -> float:
    """今天还有几小时活跃窗口."""
    now = datetime.now(timezone.utc)
    hours_map = persona.get("active_hours") or {}
    weekday = now.weekday()
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    today_windows = hours_map.get(weekdays[weekday], [])
    if not today_windows:
        return 0.5  # fallback
    end_hours = [end_h for _, end_h in today_windows]
    last_end = max(end_hours)
    return max(0.5, last_end - now.hour)


async def chitchat_scheduler_tick() -> int:
    """主 tick: 处理条数 (实际入队)。"""
    accounts = _list_active_worker_accounts()
    processed = 0
    pending_dispatches = []  # 收集待 await 的 dispatch 协程
    for account in accounts:
        chats = _list_joined_chats_for_account(account)
        if not chats:
            continue
        with Session(engine) as session:
            persona = get_persona_for_account(session=session, account_id=account.id)
        if persona.get("daily_chitchat_quota", 0) <= 0:
            continue

        for chat_id, include_kws in chats:
            sent_today = _chitchat_log_count_today(account_id=account.id, chat_id=chat_id)
            recent_biz = _has_recent_business_reply(account_id=account.id, chat_id=chat_id)
            hours_left = _hours_left_today(persona)
            decision = _decide_to_chitchat(
                persona=persona, sent_today_count=sent_today,
                hours_left_today=hours_left, recent_business_reply=recent_biz,
            )
            if not decision["fire"]:
                continue

            topic = _pick_random_chitchat_topic()
            if topic is None:
                continue
            if _topic_hits_monitor_keywords(topic, include_kws):
                # 跳过, 避免触发自家 LeadDetector
                continue

            text = await _llm_render_chitchat(topic.prompt_template, persona)
            if not text:
                continue

            # 反幻觉: identity-exposure 词过滤 (复用 reply_composer)
            from app.services.reply_composer import _has_identity_exposure
            if _has_identity_exposure(text):
                continue
            # 二次校验: 渲染后的 text 也不能命中关键词
            text_lower = text.lower()
            if any(kw.lower() in text_lower for kw in include_kws):
                continue

            # 随机时延
            typing_delay = random.randint(*persona["typing_delay_seconds_range"])
            # 收集协程, 稍后统一 gather (避免 asyncio.run() 提前取消 pending tasks)
            pending_dispatches.append(dispatch_chitchat(
                account_id=account.id, chat_id=chat_id, topic_id=topic.id,
                text=text, typing_delay=typing_delay,
            ))
            processed += 1

    # 在 return 前 await 所有 dispatch (typing_delay 期间不阻塞其他账号决策)
    if pending_dispatches:
        await asyncio.gather(*pending_dispatches, return_exceptions=True)
    return processed


@celery_app.task(name="chitchat_scheduler.tick")
def chitchat_tick():
    return asyncio.run(chitchat_scheduler_tick())
