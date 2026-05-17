import re
import logging
import asyncio
import json
import random
from typing import List, Optional
from sqlmodel import Session, select
from app.core.db import engine
from app.core.celery_app import celery_app
from app.core.concurrency import redis_client
from app.models.account import Account
from app.models.ai_persona import AIPersona
from app.models.keyword_monitor import KeywordMonitor, KeywordHit
from app.models.script import Script
from app.services.telegram_client import send_message_with_client, _create_client_and_run

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anti-hallucination guard (also duplicated in monitor_tasks.py to avoid
# circular imports at task-discovery time)
# ---------------------------------------------------------------------------
HALLUCINATION_RE = re.compile(
    r'(作为.{0,4}AI|我是.{0,4}(AI|助手|语言模型)|'
    r'无法提供|对不起，我|抱歉，我|我无法|我没有能力|'
    r'请注意我是|根据我的训练|as an AI)',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# LLM prompt templates for Director-Actor mode
# ---------------------------------------------------------------------------

# 全局人类化注入：所有 persona 都共享的"真人感"基础规则
# 让 LLM 输出更像真人、有情绪、有生活感、不像 AI 客服
_HUMAN_TRAITS = """[人类化基础规则 - 必须遵守]

1. 你是一个真实的人，有家庭、工作、情绪、疲惫、烦躁。不是助手、不是客服、不是机器人。

2. 时间感知（按当前时间段调整状态）：
   - 早上 (6-9 点)：刚醒/在挤地铁，话短、偶尔提"刚泡咖啡""地铁信号差"
   - 上午 (9-12 点)：正在忙，回得快但简短
   - 中午 (12-14 点)：吃饭/午休，可能提"刚吃完""在外卖"
   - 下午 (14-18 点)：工作中，专业感稍强但不死板
   - 晚上 (18-22 点)：放松状态，话多一点，可能提"刚到家""今天有点累"
   - 深夜 (22-2 点)：少话，偶尔提"还没睡""失眠了"

3. 真人打字习惯：
   - 不要总用规范标点。多用空格断句、少用"。"，偶尔不加标点直接回
   - 偶尔有错别字（不要刻意修正，1 条里最多 1 个）
   - 偶尔用拼音首字母/缩写：yyds、nbcs、ggww、xswl、awsl
   - 短句多于长句。一条 30-60 字最自然

4. 真人情绪：
   - 心情不好时回得短而冷
   - 周末/晚上更松弛，工作日白天更利索
   - 偶尔吐槽天气、堵车、外卖、加班，让对话有"生活感"
   - 不要永远积极向上，可以无奈、烦躁、自嘲一下
   - 收到不熟悉的话题可以说"这个我不太懂""没研究过"，比假装专业更真实

5. 真人反应：
   - 不要每条都立刻回热情接茬。偶尔可以"我刚开会出来""刚回家""刚才在带娃"
   - 偶尔自嘲："我真是老了""脑子不够用""卷不动了"
   - 偶尔表达情绪："唉""真的服了""绝了""离谱"

6. 绝对禁止：
   - "作为AI/我是助手/抱歉/无法提供/我没有能力/请注意我是"等任何 AI 暴露词
   - 过度热情的客服话术（"亲爱的""为您服务""很高兴帮助您"）
   - 完美无缺的回答（真人会有犹豫、不确定）
"""

_FREE_CHAT_PROMPT = (
    "{persona_prompt}\n\n"
    "{human_traits}\n\n"
    "[当前任务]\n"
    "你正在一个 Telegram 群里，话题是：{topic}\n"
    "群里最近的消息：\n{recent_msgs}\n\n"
    "请按你的人设，自然地说一条话参与这个话题的讨论。\n"
    "可以是观点、疑问、经验分享、附和、吐槽——只要符合你的性格。\n\n"
    "[硬约束]\n"
    "- 20-80 字\n"
    "- 不要任何 AI 暴露词\n"
    "- 只输出消息内容，不要解释、不要引号、不要 markdown\n"
)

_DIRECTOR_PROMPTS = {
    # Role A: 提问/捧哏 角色
    "role_a": (
        "{persona_prompt}\n\n"
        "{human_traits}\n\n"
        "[当前任务]\n"
        "你正在一个 Telegram 群里。最近的群聊背景：\n{context}\n\n"
        "刚刚有人发了：{trigger}\n\n"
        "请按你上面的人设和性格、以及人类化基础规则，自然地跟帖一条消息回应。\n"
        "你的角色定位是「提问/好奇/捧哏方」——可以是疑问、感叹、附和、或表示感兴趣。\n"
        "知识背景（如自然可融入）：{knowledge}\n\n"
        "[硬约束]\n"
        "- 不超过 60 字\n"
        "- 不要任何 AI 暴露词（具体见上述「绝对禁止」）\n"
        "- 只输出消息内容，不要解释、不要引号、不要 markdown\n"
    ),
    # Role B: 专家/解答 角色
    "role_b": (
        "{persona_prompt}\n\n"
        "{human_traits}\n\n"
        "[当前任务]\n"
        "你正在一个 Telegram 群里。最近的群聊背景：\n{context}\n\n"
        "话题触发消息：{trigger}\n"
        "刚才群友问了一句：{role_a_msg}\n\n"
        "请按你上面的人设和性格、以及人类化基础规则，自然地回应这个问题。\n"
        "你的角色定位是「专家/解答方」——可以分享经验、给出洞察、引导讨论。\n"
        "如有专业知识请用自己的话融入（勿照搬）：{knowledge}\n\n"
        "[硬约束]\n"
        "- 不超过 100 字\n"
        "- 不要任何 AI 暴露词（具体见上述「绝对禁止」）\n"
        "- 只输出消息内容，不要解释、不要引号、不要 markdown\n"
    ),
}


def _anti_hallucination_filter(text: str) -> str:
    """Return text unchanged; return '' if hallucination patterns detected."""
    if not text:
        return ""
    if HALLUCINATION_RE.search(text):
        logger.warning(f"Hallucination filter triggered: {text[:80]!r}")
        return ""
    return text.strip()


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

class ShillDispatcher:
    def __init__(self):
        pass

    async def dispatch_shill(self, hit_id: int):
        """
        Entry point for passive-marketing keyword hits.
        Routes to static-script mode (trigger_script) or AI mode (trigger_ai).
        """
        with Session(engine) as session:
            hit = session.get(KeywordHit, hit_id)
            if not hit:
                logger.error(f"Hit {hit_id} not found")
                return

            monitor = session.get(KeywordMonitor, hit.keyword_monitor_id)
            if not monitor:
                logger.error(f"Monitor {hit.keyword_monitor_id} not found")
                return

            if monitor.action_type == "trigger_script":
                await self._dispatch_script_shill(hit, monitor, session)
            else:
                logger.info(
                    f"Monitor {monitor.id} action_type={monitor.action_type!r}, "
                    "not a shill action"
                )

    async def dispatch_ai_shill(self, hit_id: int, context_msgs: List[str]):
        """
        Director-Actor AI mode entry point.
        Called directly from listener_service when action_type == 'trigger_ai'.
        context_msgs: recent group messages (already sliced by caller).
        """
        with Session(engine) as session:
            hit = session.get(KeywordHit, hit_id)
            if not hit:
                logger.error(f"Hit {hit_id} not found")
                return

            monitor = session.get(KeywordMonitor, hit.keyword_monitor_id)
            if not monitor:
                logger.error(f"Monitor {hit.keyword_monitor_id} not found")
                return

            await self._dispatch_ai_shill(hit, monitor, session, context_msgs)

    # ------------------------------------------------------------------
    # Static-script path (unchanged logic, extracted for clarity)
    # ------------------------------------------------------------------

    async def _dispatch_script_shill(
        self,
        hit: KeywordHit,
        monitor: KeywordMonitor,
        session: Session,
    ):
        if not monitor.reply_script_id:
            logger.warning(f"No reply script configured for monitor {monitor.id}")
            return

        script = session.get(Script, monitor.reply_script_id)
        if not script:
            logger.error(f"Script {monitor.reply_script_id} not found")
            return

        shill_accounts = session.exec(
            select(Account).where(
                Account.tier == "tier2",
                Account.status == "active",
            )
        ).all()

        if not shill_accounts:
            logger.warning("No Tier 2 shill accounts available")
            return

        try:
            roles = json.loads(script.roles_json)
            lines = json.loads(script.lines_json)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(f"Invalid script JSON: {e}")
            return

        if not roles or not lines:
            return

        if len(shill_accounts) < len(roles):
            logger.warning(
                f"Not enough shill accounts. Need {len(roles)}, have {len(shill_accounts)}"
            )
            return

        selected = random.sample(list(shill_accounts), len(roles))
        role_map = {role["name"]: selected[i] for i, role in enumerate(roles)}
        logger.info(f"Assigned shill accounts for Hit {hit.id}: {role_map}")

        celery_app.send_task(
            "app.tasks.monitor_tasks.execute_shill_conversation",
            args=[hit.id, script.id, {k: v.id for k, v in role_map.items()}],
        )

        hit.status = "handling"
        session.add(hit)
        session.commit()

    # ------------------------------------------------------------------
    # Director-Actor AI path
    # ------------------------------------------------------------------

    async def _dispatch_ai_shill(
        self,
        hit: KeywordHit,
        monitor: KeywordMonitor,
        session: Session,
        context_msgs: List[str],
    ):
        group_id = hit.source_group_id

        # 1. Distributed lock — 60 s cooldown per group
        lock_key = f"chat_cooldown:{group_id}"
        acquired = redis_client.set(lock_key, "1", nx=True, ex=60)
        if not acquired:
            logger.info(
                f"Group {group_id} in AI-shill cooldown (60s), skipping Hit {hit.id}"
            )
            return

        # 2. Select 2 active tier2 accounts
        candidates = list(
            session.exec(
                select(Account).where(
                    Account.tier == "tier2",
                    Account.status == "active",
                )
            ).all()
        )

        if len(candidates) < 2:
            logger.warning(
                f"Not enough tier2 accounts for AI shill (need 2, have {len(candidates)})"
            )
            return

        account_a, account_b = random.sample(candidates, 2)

        # 3. Assemble LLM context
        context_text = "\n".join(context_msgs) if context_msgs else "（暂无历史消息）"
        trigger_text = hit.message_content or ""

        # Persona + knowledge
        # 关键修复：使用 persona.system_prompt 作为完整人设上下文，而非仅 tone
        persona = (
            session.get(AIPersona, monitor.ai_persona_id)
            if monitor.ai_persona_id
            else None
        )
        persona_prompt = (
            persona.system_prompt
            if persona and persona.system_prompt
            else "你是一个普通的 Telegram 群友，性格友好自然。"
        )

        from app.services.ai_engine import AIEngine
        knowledge = (
            AIEngine.get_campaign_knowledge(session, monitor.campaign_id)
            if monitor.campaign_id
            else ""
        )

        ai = AIEngine(session)

        # 4a. Generate Role A (questioner)
        try:
            raw_a = await ai.llm.generate(
                _DIRECTOR_PROMPTS["role_a"].format(
                    persona_prompt=persona_prompt,
                    human_traits=_HUMAN_TRAITS,
                    context=context_text,
                    trigger=trigger_text,
                    knowledge=knowledge or "无",
                )
            )
            text_a = _anti_hallucination_filter(raw_a)
        except Exception as e:
            logger.error(f"LLM role_a generation failed: {e}")
            text_a = ""

        # 4b. Generate Role B (expert), referencing A's upcoming message
        try:
            raw_b = await ai.llm.generate(
                _DIRECTOR_PROMPTS["role_b"].format(
                    persona_prompt=persona_prompt,
                    human_traits=_HUMAN_TRAITS,
                    context=context_text,
                    trigger=trigger_text,
                    role_a_msg=text_a or "（提问中）",
                    knowledge=knowledge or "无",
                )
            )
            text_b = _anti_hallucination_filter(raw_b)
        except Exception as e:
            logger.error(f"LLM role_b generation failed: {e}")
            text_b = ""

        if not text_a and not text_b:
            logger.warning(
                f"Both AI replies empty/filtered for Hit {hit.id}, aborting dispatch"
            )
            return

        # 5. Schedule with Celery countdown (time-separated sends)
        from app.tasks.monitor_tasks import execute_single_shill_line

        countdown_a = random.randint(5, 10)
        countdown_b = countdown_a + random.randint(15, 25)

        if text_a:
            execute_single_shill_line.apply_async(
                args=[account_a.id, group_id, text_a, int(hit.message_id)],
                countdown=countdown_a,
            )
            logger.info(
                f"Scheduled role_A (account {account_a.id}) "
                f"in {countdown_a}s for Hit {hit.id}"
            )

        if text_b:
            execute_single_shill_line.apply_async(
                args=[account_b.id, group_id, text_b, None],
                countdown=countdown_b,
            )
            logger.info(
                f"Scheduled role_B (account {account_b.id}) "
                f"in {countdown_b}s for Hit {hit.id}"
            )

        hit.status = "handling"
        session.add(hit)
        session.commit()


# ---------------------------------------------------------------------------
# Worker-side conversation runner (static-script mode)
# ---------------------------------------------------------------------------

async def run_shill_conversation(hit_id: int, script_id: int, role_account_ids: dict):
    """
    Executes a multi-turn static-script conversation.
    role_account_ids: {"RoleA": 123, "RoleB": 456}
    """
    logger.info(f"Starting shill conversation for Hit {hit_id}")

    with Session(engine) as session:
        hit = session.get(KeywordHit, hit_id)
        script = session.get(Script, script_id)

        if not hit or not script:
            return

        lines = json.loads(script.lines_json)
        message_id_map = {-1: int(hit.message_id)}

        for i, line in enumerate(lines):
            role_name = line["role"]
            content = line["content"]
            reply_idx = line.get("reply_to_line_index")

            account_id = role_account_ids.get(role_name)
            if not account_id:
                continue

            account = session.get(Account, account_id)
            if not account:
                continue

            delay = random.uniform(5, 12) if i == 0 else random.uniform(15, 45)
            logger.info(f"Shill: Waiting {delay:.1f}s before line {i}...")
            await asyncio.sleep(delay)

            reply_to_id = None
            if i == 0:
                reply_to_id = int(hit.message_id)
            elif reply_idx is not None:
                reply_to_id = message_id_map.get(reply_idx)

            target = hit.source_group_id

            success, result = await send_message_with_client_reply(
                account,
                target,
                content,
                reply_to_message_id=reply_to_id,
                db_session=session,
            )

            if success:
                try:
                    message_id_map[i] = int(result)
                except (ValueError, TypeError):
                    pass
            else:
                logger.error(f"Shill failed to send line {i}: {result}")

        hit.status = "handled"
        session.add(hit)
        session.commit()


async def dispatch_free_conversation(
    account_ids: List[int],
    chat_id: str,
    topic: str,
    turns_per_account: int = 1,
    recent_msgs: Optional[List[str]] = None,
) -> tuple[int, int]:  # (scheduled_count, total_duration_seconds)
    """
    Generate persona-based messages for each account and schedule them
    with staggered Celery countdowns. Returns total scheduled duration (seconds).
    """
    from app.tasks.monitor_tasks import execute_single_shill_line
    from app.services.ai_engine import AIEngine

    with Session(engine) as session:
        ai = AIEngine(session)
        recent_text = "\n".join(recent_msgs) if recent_msgs else "（群聊刚开始）"
        countdown = 5
        scheduled_count = 0

        accounts = []
        for aid in account_ids:
            acc = session.get(Account, aid)
            if acc and acc.status == "active":
                accounts.append(acc)

        if not accounts:
            logger.warning("dispatch_free_conversation: no active accounts found")
            return 0, 0

        for turn in range(turns_per_account):
            turn_accounts = list(accounts)
            random.shuffle(turn_accounts)

            for acc in turn_accounts:
                persona = (
                    session.get(AIPersona, acc.ai_persona_id)
                    if acc.ai_persona_id
                    else None
                )
                persona_prompt = (
                    persona.system_prompt
                    if persona and persona.system_prompt
                    else "你是一个普通的 Telegram 群友，性格自然随和。"
                )

                try:
                    raw = await ai.llm.generate(
                        _FREE_CHAT_PROMPT.format(
                            persona_prompt=persona_prompt,
                            human_traits=_HUMAN_TRAITS,
                            topic=topic,
                            recent_msgs=recent_text,
                        )
                    )
                    text = _anti_hallucination_filter(raw)
                except Exception as e:
                    logger.error(f"LLM failed for account {acc.id}: {e}")
                    text = ""

                if not text:
                    # Still advance countdown so timing between actual sends stays natural
                    await asyncio.sleep(13)  # stay under 5 req/min free-tier limit
                    continue

                execute_single_shill_line.apply_async(
                    args=[acc.id, chat_id, text, None],
                    countdown=countdown,
                )
                scheduled_count += 1
                logger.info(
                    f"dispatch_free_conversation: account={acc.id} "
                    f"persona={persona.name if persona else 'none'} "
                    f"scheduled in {countdown}s: {text[:40]!r}"
                )
                countdown += random.randint(30, 90)
                # Respect Gemini free-tier: 5 req/min → ≥13s between calls
                await asyncio.sleep(13)

    return scheduled_count, countdown


async def send_message_with_client_reply(
    account: Account,
    chat_id: str,
    text: str,
    reply_to_message_id: Optional[int] = None,
    db_session: Session = None,
):
    """
    Send a message with optional reply threading; returns (success, message_id_str).
    """
    async def op(client):
        try:
            target = int(chat_id)
        except (ValueError, TypeError):
            target = chat_id

        # 预热 peers 缓存（同 execute_single_shill_line）
        try:
            async for _ in client.get_dialogs(limit=50):
                pass
        except Exception:
            pass

        msg = await client.send_message(
            chat_id=target,
            text=text,
            reply_to_message_id=reply_to_message_id,
        )
        return msg.id

    try:
        success, res = await _create_client_and_run(
            account, op, db_session=db_session
        )
        return success, res
    except Exception as e:
        return False, str(e)
