"""
ConversationDirector — 多账号动态对话引擎

每条群消息到来时：
1. 更新群上下文（带发言人名称，存 Redis）
2. 按角色概率 + 时间段 + 冷却 选出 0-2 个账号
3. 对每个账号：LLM 用其人设决定"回不回 / 说什么"（SKIP 则跳过）
4. 用 execute_single_shill_line Celery 任务在随机延迟后发出

主动发言：proactive_speak(group_id) 由 Beat 定时调用，
让账号主动打破沉默，发起话题。
"""
import json
import time
import random
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Set

from sqlmodel import Session, select

from app.core.db import engine
from app.core.concurrency import redis_client
from app.models.account import Account
from app.models.ai_persona import AIPersona

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────────────────────
ACCOUNT_COOLDOWN_SEC = 12 * 60    # 每账号每群 12 分钟冷却
GROUP_GATE_SEC = 3 * 60           # 群级节流：3 分钟内最多触发一次 Director
CTX_WINDOW = 20                   # 上下文保留条数
CTX_TTL = 86400                   # 24h

# 各角色响应概率
_ROLE_PROBS = {
    "actor":  0.65,
    "cannon": 0.28,
    "scout":  0.05,   # scout 专心监听，极少插嘴
    "sniper": 0.40,
}

# ── Prompts ────────────────────────────────────────────────────────────────────
_HUMAN_TRAITS_SHORT = """[真人基础规则]
- 短句为主，偶尔省略标点
- 偶尔错别字、缩写（yyds/xswl/awsl）
- 有情绪、有疲惫、有生活感，不是客服
- 绝对禁止：作为AI/我是助手/抱歉/无法提供"""

_REACT_PROMPT = """\
{persona_prompt}

{human_traits}

[当前场景]
时间：{time_str}。你在一个 Telegram 群里。

最近的群聊（从早到晚）：
{context}

{sender_name} 刚说："{trigger}"

[你的任务]
以你的人设和性格，判断：
① 你现在会看到这条消息吗？（考虑时间、你是否关注这话题、你忙不忙）
② 如果看到了，你会有什么反应？

输出规则（只选一条）：
- 不感兴趣 / 没空 / 没话说 → 只输出：SKIP
- 有话说 → 直接输出你要说的（20-80 字，真人口吻，不解释，不加引号）\
"""

_PROACTIVE_PROMPT = """\
{persona_prompt}

{human_traits}

[当前场景]
时间：{time_str}。你在一个 Telegram 群里，最近群里有点安静。

群里最近的消息：
{context}

你刚刚打开手机，想随手在群里说点什么。
可以是：最近遇到的事 / 和你领域相关的观点 / 随便吐槽 / 问个小问题。
话题参考：{topic_hint}

输出规则：
- 直接输出你要说的（20-80 字，真人口吻）
- 不要解释，不要引号，不要 markdown，不要 AI 暴露词\
"""


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def _get_time_str() -> str:
    h = datetime.now().hour
    if 6 <= h < 9:   return f"早上 {h} 点，刚起床"
    if 9 <= h < 12:  return f"上午 {h} 点，工作中"
    if 12 <= h < 14: return "中午，吃饭/午休"
    if 14 <= h < 18: return f"下午 {h} 点"
    if 18 <= h < 21: return f"晚上 {h} 点，刚下班放松"
    if 21 <= h < 23: return f"晚上 {h} 点，休闲时间"
    return f"深夜 {h} 点"


def _time_multiplier() -> float:
    h = datetime.now().hour
    if 0 <= h < 7:   return 0.15   # 深夜极少响应
    if 7 <= h < 9:   return 0.50
    if 9 <= h < 22:  return 1.00
    if 22 <= h < 24: return 0.55
    return 1.0


# ── 主类 ───────────────────────────────────────────────────────────────────────

class ConversationDirector:
    """多账号动态群聊引擎，由 ListenerService 实例化并持有。"""

    def __init__(self):
        # 由 ListenerService 启动后填充，避免我们账号互相回复
        self.our_tg_ids: Set[str] = set()

    # ── Redis key helpers ──────────────────────────────────────────────────────

    def _ctx_key(self, gid: str) -> str:
        return f"dir_ctx:{gid}"

    def _acct_cd_key(self, account_id: int, gid: str) -> str:
        return f"dir_cd:{account_id}:{gid}"

    def _group_gate_key(self, gid: str) -> str:
        return f"dir_gate:{gid}"

    def _live_groups_key(self) -> str:
        return "dir_live_groups"

    # ── Live-chat group registry ───────────────────────────────────────────────

    def enable_group(self, group_id: str):
        redis_client.sadd(self._live_groups_key(), group_id)

    def disable_group(self, group_id: str):
        redis_client.srem(self._live_groups_key(), group_id)

    def is_group_enabled(self, group_id: str) -> bool:
        return bool(redis_client.sismember(self._live_groups_key(), group_id))

    def list_groups(self) -> List[str]:
        members = redis_client.smembers(self._live_groups_key())
        return [g.decode() if isinstance(g, bytes) else g for g in members]

    # ── Context management ─────────────────────────────────────────────────────

    def push_context(self, group_id: str, sender_name: str, text: str, msg_id: int):
        """所有消息（包括自己发的）都入上下文。"""
        entry = json.dumps({"n": sender_name, "t": text[:200], "id": msg_id,
                            "ts": int(time.time())}, ensure_ascii=False)
        key = self._ctx_key(group_id)
        pipe = redis_client.pipeline()
        pipe.rpush(key, entry)
        pipe.ltrim(key, -CTX_WINDOW, -1)
        pipe.expire(key, CTX_TTL)
        pipe.execute()

        # 记录活跃群列表（供主动发言任务使用）
        redis_client.zadd("dir_active_groups", {group_id: time.time()})
        redis_client.expire("dir_active_groups", CTX_TTL * 7)

    def _get_context(self, group_id: str) -> List[dict]:
        raw = redis_client.lrange(self._ctx_key(group_id), 0, -1)
        result = []
        for r in raw:
            try:
                result.append(json.loads(r))
            except Exception:
                pass
        return result

    def _fmt_context(self, ctx: List[dict]) -> str:
        if not ctx:
            return "（暂无历史消息）"
        return "\n".join(f"{c['n']}: {c['t']}" for c in ctx)

    # ── Cooldown ───────────────────────────────────────────────────────────────

    def _is_on_cooldown(self, account_id: int, group_id: str) -> bool:
        return redis_client.exists(self._acct_cd_key(account_id, group_id)) > 0

    def _set_cooldown(self, account_id: int, group_id: str,
                      seconds: int = ACCOUNT_COOLDOWN_SEC):
        redis_client.setex(self._acct_cd_key(account_id, group_id), seconds, "1")

    def _group_gate_pass(self, group_id: str) -> bool:
        """群级节流：3 分钟内只触发一次 Director LLM 调用。"""
        key = self._group_gate_key(group_id)
        if redis_client.exists(key):
            return False
        redis_client.setex(key, GROUP_GATE_SEC, "1")
        return True

    # ── Responder selection ────────────────────────────────────────────────────

    def _select_responders(self, group_id: str, sender_id: str) -> List[Account]:
        t_mult = _time_multiplier()
        candidates = []

        with Session(engine) as session:
            accounts = session.exec(
                select(Account).where(Account.status == "active")
            ).all()

            for acc in accounts:
                if self._is_on_cooldown(acc.id, group_id):
                    continue
                base = _ROLE_PROBS.get(acc.combat_role or "cannon", 0.2)
                if random.random() < base * t_mult:
                    candidates.append(Account.model_validate(acc))

        # 优先 actor，最多 2 个
        candidates.sort(key=lambda a: (0 if a.combat_role == "actor" else 1, random.random()))
        return candidates[:2]

    # ── LLM response generation ────────────────────────────────────────────────

    async def _generate_reply(
        self,
        account: Account,
        context_str: str,
        sender_name: str,
        trigger: str,
    ) -> Optional[str]:
        from app.services.ai_engine import AIEngine
        from app.services.shill_dispatcher import _anti_hallucination_filter
        from app.services.kb_retrieval import retrieve_relevant_kb, format_kb_for_prompt

        with Session(engine) as session:
            persona = session.get(AIPersona, account.ai_persona_id) if account.ai_persona_id else None
            persona_prompt = (persona.system_prompt if persona and persona.system_prompt
                              else "你是一个普通的 Telegram 群友，性格自然随和。")

            # RAG：从知识库向量召回相关条目注入 persona prompt
            kb_items = await retrieve_relevant_kb(session, trigger, top_k=4)
            kb_block = format_kb_for_prompt(kb_items, max_chars=1200)
            if kb_block:
                persona_prompt = (
                    f"{persona_prompt}\n\n"
                    f"[业务知识参考 — 如果用户提到相关内容，可以基于这些回答]\n{kb_block}"
                )

            ai = AIEngine(session)
            try:
                raw = await ai.llm.generate(
                    _REACT_PROMPT.format(
                        persona_prompt=persona_prompt,
                        human_traits=_HUMAN_TRAITS_SHORT,
                        time_str=_get_time_str(),
                        context=context_str,
                        sender_name=sender_name,
                        trigger=trigger[:150],
                    )
                )
            except Exception as e:
                logger.error(f"Director LLM failed account={account.id}: {e}")
                return None

        if not raw:
            return None
        stripped = raw.strip()
        if stripped.upper() == "SKIP" or stripped.upper().startswith("SKIP"):
            logger.debug(f"account={account.id} chose SKIP")
            return None

        return _anti_hallucination_filter(stripped) or None

    # ── Public: reactive ───────────────────────────────────────────────────────

    async def handle_message(
        self,
        group_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        msg_id: int,
    ):
        """ListenerService 对每条新消息调用此方法。"""
        # 1. 更新上下文（自己发的消息也记录，保持对话连贯）
        self.push_context(group_id, sender_name, text, msg_id)

        # 2. 不响应自己
        if str(sender_id) in self.our_tg_ids:
            return

        # 3. 群级节流（3 分钟内只处理一次）
        if not self._group_gate_pass(group_id):
            return

        # 4. 选出响应账号
        responders = self._select_responders(group_id, sender_id)
        if not responders:
            return

        ctx = self._get_context(group_id)
        # 排除刚收到的这条（已在末尾），取前面的作为背景
        context_str = self._fmt_context(ctx[:-1])

        from app.tasks.monitor_tasks import execute_single_shill_line

        base_delay = 0
        for acc in responders:
            reply = await self._generate_reply(acc, context_str, sender_name, text)
            if not reply:
                continue

            # actor 2-8 min，cannon 5-15 min
            if acc.combat_role == "actor":
                delay = base_delay + random.randint(120, 480)
            else:
                delay = base_delay + random.randint(300, 900)

            execute_single_shill_line.apply_async(
                args=[acc.id, group_id, reply, msg_id],
                countdown=delay,
            )
            self._set_cooldown(acc.id, group_id)
            base_delay = delay + random.randint(60, 180)

            logger.info(
                f"Director reactive: account={acc.id} group={group_id} "
                f"in {delay//60}m{delay%60}s: {reply[:50]!r}"
            )

            # Gemini 免费层节流：两次 LLM 调用之间留 13s
            await asyncio.sleep(13)

    # ── Public: proactive ──────────────────────────────────────────────────────

    async def proactive_speak(self, group_id: str):
        """Beat 定时任务调用：让某个账号主动发起话题。"""
        ctx = self._get_context(group_id)

        # 群最近 2 小时内有消息才值得主动发言
        if ctx:
            last_ts = ctx[-1].get("ts", 0)
            if time.time() - last_ts > 7200:
                logger.debug(f"proactive_speak: group {group_id} quiet >2h, skipping")
                return
        elif not ctx:
            logger.debug(f"proactive_speak: group {group_id} has no context, skipping")
            return

        context_str = self._fmt_context(ctx)

        with Session(engine) as session:
            accounts = list(session.exec(
                select(Account).where(Account.status == "active")
            ).all())

        candidates = [
            a for a in accounts
            if a.ai_persona_id and not self._is_on_cooldown(a.id, group_id)
        ]
        if not candidates:
            logger.debug(f"proactive_speak: no available accounts for group {group_id}")
            return

        acc = random.choice(candidates)

        from app.services.ai_engine import AIEngine
        from app.services.shill_dispatcher import _anti_hallucination_filter

        with Session(engine) as session:
            persona = session.get(AIPersona, acc.ai_persona_id)
            persona_prompt = (persona.system_prompt if persona and persona.system_prompt
                              else "你是一个普通的群友。")
            topic_hint = persona.name if persona else "日常话题"
            ai = AIEngine(session)
            try:
                raw = await ai.llm.generate(
                    _PROACTIVE_PROMPT.format(
                        persona_prompt=persona_prompt,
                        human_traits=_HUMAN_TRAITS_SHORT,
                        time_str=_get_time_str(),
                        context=context_str,
                        topic_hint=topic_hint,
                    )
                )
            except Exception as e:
                logger.error(f"Director proactive LLM failed account={acc.id}: {e}")
                return

        if not raw or raw.strip().upper().startswith("SKIP"):
            return

        text = _anti_hallucination_filter(raw.strip())
        if not text:
            return

        from app.tasks.monitor_tasks import execute_single_shill_line
        delay = random.randint(30, 180)
        execute_single_shill_line.apply_async(
            args=[acc.id, group_id, text, None],
            countdown=delay,
        )
        self._set_cooldown(acc.id, group_id)

        logger.info(
            f"Director proactive: account={acc.id} group={group_id} "
            f"in {delay}s: {text[:50]!r}"
        )
