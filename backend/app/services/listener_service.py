"""
监听服务 - 增强版
支持被动式营销（方案A两级过滤）和主动式营销（随机延迟+账号轮询+熔断）
"""
import logging
import asyncio
import time
import re
import json
import random
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from sqlmodel import Session, select
from pyrogram import Client, filters, idle, enums
from pyrogram.handlers import MessageHandler
from app.core.db import engine
from app.models.account import Account
from app.models.keyword_monitor import KeywordMonitor, KeywordHit
from app.services.telegram_client import get_proxy_dict, _create_client_and_run
from app.services.keyword_monitor_service import KeywordMonitorService
from app.services.score_service import ScoreService

logger = logging.getLogger(__name__)


# AI 人设预设 Prompt
AI_PERSONA_PROMPTS = {
    "helpful": "你是一个热心的群友，语气随意友善。看到有人问问题，就简单分享自己的经验或推荐。不要带链接，引导对方看签名或私聊。",
    "expert": "你是这个领域的资深从业者，语气专业但不高傲。用简洁的话回答问题，偶尔分享一点干货。",
    "curious": "你是一个好奇的新人，对话题很感兴趣。你可以追问细节或者附和别人的观点。",
    "custom": None  # 使用 ai_reply_prompt 自定义
}


class ListenerService:
    def __init__(self):
        self.clients: List[Client] = []
        self.client_accounts: Dict[str, Account] = {}  # client_name -> Account (用于账号轮询)
        self.monitors: List[KeywordMonitor] = []
        self.monitor_service: KeywordMonitorService = None

        # 冷却时间记录: key = f"{monitor_id}_{chat_id}", value = last_trigger_timestamp
        self.cooldowns: Dict[str, float] = {}

        # 上下文缓存: key = chat_id, value = List of recent messages (保留兼容)
        self.context_cache: Dict[int, List[str]] = {}
        self.context_max_size = 10

        # ConversationDirector — 动态对话引擎
        from app.services.conversation_director import ConversationDirector
        self.director = ConversationDirector()
        self._our_tg_ids: set = set()   # 我们自己账号的 Telegram user_id

        # active_monitors 内存缓存：避免每条消息打一次 DB。
        # 1000+ 账号 × 群活跃度可能 ≥ 几千 QPS，按 30s TTL 刷新已足够。
        self._monitors_cache: List[KeywordMonitor] = []
        self._monitors_cache_ts: float = 0.0
        self._monitors_cache_ttl: float = 30.0

    def _get_active_monitors(self, session: Session) -> List[KeywordMonitor]:
        """返回缓存的 active monitors；过期则刷新。"""
        now = time.time()
        if now - self._monitors_cache_ts > self._monitors_cache_ttl:
            self._monitors_cache = list(session.exec(
                select(KeywordMonitor).where(KeywordMonitor.is_active == True)
            ).all())
            self._monitors_cache_ts = now
        return self._monitors_cache

    async def _handle_message(self, client: Client, message):
        """
        消息处理核心逻辑 - 支持被动式(两级过滤)和主动式营销，以及动态对话
        """
        if not message.text:
            return

        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0
        sender_name = (message.from_user.first_name if message.from_user else "") or str(user_id)

        # 旧上下文缓存（兼容 dispatch_ai_shill）
        if chat_id not in self.context_cache:
            self.context_cache[chat_id] = []
        self.context_cache[chat_id].append(message.text)
        if len(self.context_cache[chat_id]) > self.context_max_size:
            self.context_cache[chat_id].pop(0)

        # ── ConversationDirector：如果该群已开启 live-chat，异步处理 ──────────
        group_id_str = str(chat_id)
        if self.director.is_group_enabled(group_id_str):
            asyncio.create_task(
                self.director.handle_message(
                    group_id=group_id_str,
                    sender_id=str(user_id),
                    sender_name=sender_name,
                    text=message.text,
                    msg_id=message.id,
                )
            )

        with Session(engine) as session:
            active_monitors = self._get_active_monitors(session)

            chat_title = message.chat.title or str(chat_id)
            username = message.from_user.username if message.from_user else ""
            first_name = message.from_user.first_name if message.from_user else ""
            content = message.text

            for monitor in active_monitors:
                # === Step 1: 检查目标群组过滤 ===
                if not self._check_target_group(monitor, message):
                    continue
                
                # === Step 2: 关键词匹配 (根据模式选择) ===
                is_match, match_confidence = await self._check_match(
                    monitor, content, session
                )
                
                if not is_match:
                    continue
                
                # === Step 3: 冷却检查 ===
                if not self._check_cooldown(monitor, chat_id):
                    continue
                
                # === Step 4: 熔断检查 (主动营销模式) ===
                if monitor.marketing_mode == "active":
                    if not self._check_circuit_breaker(monitor, session):
                        logger.warning(f"Monitor {monitor.id} hit daily limit, skipping")
                        continue

                # ===== 命中确认 =====
                logger.info(f"{'[主动]' if monitor.marketing_mode == 'active' else '[被动]'} "
                           f"Keyword Hit! [{monitor.keyword}] in {chat_title} by {username} "
                           f"(confidence: {match_confidence}%)")
                
                # 记录命中
                hit = KeywordHit(
                    keyword_monitor_id=monitor.id,
                    source_group_id=str(chat_id),
                    source_group_name=chat_title,
                    source_user_id=str(user_id),
                    source_user_name=username,
                    message_content=content,
                    message_id=str(message.id),
                    status="pending"
                )
                session.add(hit)
                session.commit()
                
                # === 执行响应动作 ===
                if monitor.marketing_mode == "active":
                    # 主动式营销
                    await self._execute_active_marketing(
                        client, message, session, monitor, hit
                    )
                else:
                    # 被动式营销
                    await self._execute_passive_marketing(
                        client, message, session, monitor, hit, user_id, username, first_name
                    )

    def _check_target_group(self, monitor: KeywordMonitor, message) -> bool:
        """检查消息是否来自目标群组"""
        if not monitor.target_groups:
            return True  # 未配置则监听所有群
        
        chat_id = message.chat.id
        current_chat_username = message.chat.username
        targets = [t.strip() for t in monitor.target_groups.split(",")]
        
        for t in targets:
            if str(chat_id) == t:
                return True
            if current_chat_username and t.lstrip("@") == current_chat_username:
                return True
            if "t.me/" in t and current_chat_username and current_chat_username in t:
                return True
        return False

    async def _check_match(
        self, monitor: KeywordMonitor, content: str, session: Session
    ) -> Tuple[bool, int]:
        """
        检查消息是否匹配规则
        返回: (是否匹配, 置信度0-100)
        """
        # === 语义匹配模式 (方案A两级过滤) ===
        if monitor.match_type == "semantic":
            return await self._semantic_match(monitor, content, session)
        
        # === 传统匹配模式 ===
        if monitor.match_type == "exact":
            if monitor.keyword.lower() == content.lower():
                return True, 100
        elif monitor.match_type == "regex":
            try:
                if re.search(monitor.keyword, content, re.IGNORECASE):
                    return True, 100
            except re.error:
                pass
        else:  # partial
            if monitor.keyword.lower() in content.lower():
                return True, 100
        
        return False, 0

    async def _semantic_match(
        self, monitor: KeywordMonitor, content: str, session: Session
    ) -> Tuple[bool, int]:
        """
        方案A两级过滤：语义匹配
        Level 1: 关键词粗筛 (本地快速过滤)
        Level 2: LLM 精判 (AI 理解语境)
        """
        # === Level 1: 关键词粗筛 ===
        auto_keywords = []
        if monitor.auto_keywords:
            try:
                auto_keywords = json.loads(monitor.auto_keywords)
            except (json.JSONDecodeError, TypeError, ValueError):
                auto_keywords = [k.strip() for k in monitor.auto_keywords.split(",")]
        
        # 如果有自动关键词，先进行粗筛
        if auto_keywords:
            content_lower = content.lower()
            keyword_hit = False
            for kw in auto_keywords:
                if kw.lower() in content_lower:
                    keyword_hit = True
                    break
            
            if not keyword_hit:
                # Level 1 未通过，直接丢弃
                return False, 0
            
            logger.debug(f"Level 1 passed: keyword hit in auto_keywords")
        
        # === Level 2: LLM 精判 ===
        if not monitor.scenario_description:
            # 没有场景描述，跳过 Level 2
            return True, 70
        
        try:
            from app.services.llm import LLMService
            llm = LLMService(session)
            
            prompt = f"""
判断以下消息是否符合目标业务场景。

【目标场景】{monitor.scenario_description}

【消息内容】{content}

严格按JSON格式输出：{{"match": true/false, "confidence": 0-100}}
"""
            response = await llm.get_response(
                prompt, 
                system_prompt="你是意图判别助手，只输出JSON。"
            )
            
            if response:
                # 解析 JSON
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    is_match = result.get("match", False)
                    confidence = result.get("confidence", 0)
                    threshold = monitor.similarity_threshold or 70
                    
                    if is_match and confidence >= threshold:
                        return True, confidence
                    else:
                        logger.debug(f"Level 2 rejected: confidence {confidence} < threshold {threshold}")
                        return False, confidence
        except Exception as e:
            logger.error(f"Semantic match Level 2 failed: {e}")
            # Level 2 失败时，降级为 Level 1 结果
            return True, 60
        
        return False, 0

    def _check_cooldown(self, monitor: KeywordMonitor, chat_id: int) -> bool:
        """冷却时间检查"""
        cooldown_key = f"{monitor.id}_{chat_id}"
        last_trigger = self.cooldowns.get(cooldown_key, 0)
        cooldown_secs = monitor.cooldown_seconds or 300
        
        if time.time() - last_trigger < cooldown_secs:
            return False
        
        self.cooldowns[cooldown_key] = time.time()
        return True

    def _check_circuit_breaker(self, monitor: KeywordMonitor, session: Session) -> bool:
        """
        熔断机制检查：防止单规则回复过多。
        monitor 可能来自 _monitors_cache（detached），需要 merge 到当前 session 才能 commit。
        """
        today = date.today().isoformat()

        # 把缓存的 detached 实例 attach 到当前 session 并加载最新 DB 状态
        db_monitor = session.merge(monitor)

        if db_monitor.last_reply_date != today:
            db_monitor.daily_reply_count = 0
            db_monitor.last_reply_date = today

        max_replies = db_monitor.max_replies_per_day or 10
        if db_monitor.daily_reply_count >= max_replies:
            return False

        db_monitor.daily_reply_count += 1
        session.add(db_monitor)
        session.commit()

        # 把新值同步回缓存对象，保持 30s TTL 内的一致性
        monitor.daily_reply_count = db_monitor.daily_reply_count
        monitor.last_reply_date = db_monitor.last_reply_date

        return True

    async def _execute_passive_marketing(
        self, client: Client, message, session: Session, 
        monitor: KeywordMonitor, hit: KeywordHit,
        user_id: int, username: str, first_name: str
    ):
        """
        执行被动式营销动作
        - 消息转发
        - 线索录入
        - (可选) 触发剧本
        """
        # 1. 消息转发
        if monitor.forward_target:
            await self._forward_message(client, message, monitor.forward_target)
        
        # 2. 自动线索录入与评分
        if monitor.auto_capture_lead or (monitor.score_weight and monitor.score_weight > 0):
            await self._update_user_score(
                session, user_id, username, first_name,
                str(message.chat.id), monitor.keyword, monitor.score_weight or 10
            )
        
        # 3. 触发剧本 / AI 炒群 (被动模式下通常不主动回复，但可以触发后台任务)
        if monitor.action_type == "trigger_script" and monitor.reply_script_id:
            from app.services.shill_dispatcher import ShillDispatcher
            dispatcher = ShillDispatcher()
            await dispatcher.dispatch_shill(hit.id)

        elif monitor.action_type == "trigger_ai":
            from app.services.shill_dispatcher import ShillDispatcher
            dispatcher = ShillDispatcher()
            chat_id = message.chat.id
            context_msgs = self.context_cache.get(chat_id, [])[-8:]
            await dispatcher.dispatch_ai_shill(hit.id, context_msgs)

    async def _execute_active_marketing(
        self, client: Client, message, session: Session,
        monitor: KeywordMonitor, hit: KeywordHit
    ):
        """
        执行主动式营销动作
        - 随机延迟 (模拟真人)
        - 选择回复账号 (账号轮询)
        - 生成回复 (AI 人设)
        - 发送回复 (群内/私聊)
        """
        # 1. 随机延迟
        delay_min = monitor.delay_min_seconds or 30
        delay_max = monitor.delay_max_seconds or 180
        delay = random.randint(delay_min, delay_max)
        logger.info(f"Active marketing: waiting {delay}s before reply...")
        await asyncio.sleep(delay)
        
        # 2. 选择回复账号 (账号轮询)
        reply_client = client
        if monitor.enable_account_rotation and len(self.clients) > 1:
            # 从可用 clients 中随机选一个非当前监听账号
            other_clients = [c for c in self.clients if c != client]
            if other_clients:
                reply_client = random.choice(other_clients)
                logger.info(f"Account rotation: using alternate client {reply_client.name}")
        
        # 3. 生成回复内容
        reply_text = await self._generate_ai_reply(message, session, monitor)
        if not reply_text:
            logger.warning("Failed to generate AI reply, skipping")
            return
        
        # 4. 发送回复
        try:
            if monitor.reply_mode == "private_dm":
                # 私聊模式
                await reply_client.send_message(
                    chat_id=message.from_user.id,
                    text=reply_text
                )
                logger.info(f"Sent DM to user {message.from_user.id}")
            else:
                # 群内回复模式 (默认)
                await reply_client.send_message(
                    chat_id=message.chat.id,
                    text=reply_text,
                    reply_to_message_id=message.id
                )
                logger.info(f"Sent group reply in {message.chat.id}")
            
            # 更新命中状态
            hit.status = "handled"
            session.add(hit)
            session.commit()
            
        except Exception as e:
            logger.error(f"Failed to send active marketing reply: {e}")
            hit.status = "failed"
            session.add(hit)
            session.commit()

    async def _generate_ai_reply(
        self, message, session: Session, monitor: KeywordMonitor
    ) -> Optional[str]:
        """根据 AI 人设 + 知识库生成回复"""
        try:
            from app.services.llm import LLMService
            from app.services.ai_engine import AIEngine

            llm = LLMService(session)

            # === Persona 解析优先级 ===
            # 1. monitor.ai_persona_id (直接指定的 Persona FK)
            # 2. monitor.campaign.ai_persona_id (战役默认 Persona)
            # 3. 旧的 ai_persona 字符串预设回退
            system_prompt = None

            if monitor.ai_persona_id:
                system_prompt = AIEngine.get_persona_prompt(session, monitor.ai_persona_id)

            if not system_prompt and monitor.campaign_id:
                from app.models.campaign import Campaign
                campaign = session.get(Campaign, monitor.campaign_id)
                if campaign and campaign.ai_persona_id:
                    system_prompt = AIEngine.get_persona_prompt(session, campaign.ai_persona_id)

            if not system_prompt:
                persona = monitor.ai_persona or "helpful"
                if persona == "custom" and monitor.ai_reply_prompt:
                    system_prompt = monitor.ai_reply_prompt
                else:
                    system_prompt = AI_PERSONA_PROMPTS.get(persona, AI_PERSONA_PROMPTS["helpful"])

            # === 知识库注入 ===
            knowledge = ""
            if monitor.campaign_id:
                knowledge = AIEngine.get_campaign_knowledge(session, monitor.campaign_id)

            # === 获取上下文 ===
            chat_id = message.chat.id
            context = self.context_cache.get(chat_id, [])[-5:]
            context_str = "\n".join(context) if context else "无"

            # === 使用 group_smart_reply 模板 ===
            user_prompt = AIEngine.PROMPTS["group_smart_reply"].format(
                persona_prompt=system_prompt,
                knowledge=knowledge or "无",
                context=context_str,
                message=message.text
            )

            reply = await llm.get_response(user_prompt, system_prompt=system_prompt)
            return reply

        except Exception as e:
            logger.error(f"Generate AI reply failed: {e}")
            return None

    async def _forward_message(self, client: Client, message, target: str):
        """转发命中消息到指定目标"""
        try:
            await client.forward_messages(
                chat_id=target,
                from_chat_id=message.chat.id,
                message_ids=message.id
            )
            logger.info(f"Forwarded message to {target}")
        except Exception as e:
            logger.error(f"Failed to forward message to {target}: {e}")

    async def _update_user_score(
        self, session: Session, user_id: int, username: str, first_name: str,
        source_group: str, keyword: str, score_weight: int
    ):
        """更新用户评分"""
        try:
            score_service = ScoreService(session)
            score_service.update_user_score(
                telegram_id=user_id,
                score_delta=score_weight,
                keyword=keyword,
                username=username,
                first_name=first_name,
                source_group=source_group
            )
        except Exception as e:
            logger.error(f"Failed to update user score: {e}")

    async def start(self):
        """Start all listener clients"""
        import tempfile, shutil, os
        from app.services.telegram_client import decrypted_session_file

        # 分片：1000+ 账号场景下，单进程 Pyrogram 客户端数有上限 (~200)。
        # 通过 LISTENER_SHARD_TOTAL=N + LISTENER_SHARD_INDEX=0..N-1 把账号按 id % N 切分到 N 个进程。
        # 默认 1/0 = 不分片，行为不变。
        shard_total = max(1, int(os.getenv("LISTENER_SHARD_TOTAL", "1")))
        shard_index = max(0, int(os.getenv("LISTENER_SHARD_INDEX", "0")))
        if shard_index >= shard_total:
            logger.error(f"LISTENER_SHARD_INDEX={shard_index} >= LISTENER_SHARD_TOTAL={shard_total}, exiting")
            return

        logger.info(f"Starting Listener Service (shard {shard_index}/{shard_total})...")

        # 创建统一的临时工作目录，存放解密后的 session 文件
        temp_workdir = tempfile.mkdtemp(prefix="tgsc_listener_")
        logger.info(f"Temp session workdir: {temp_workdir}")

        try:
            with Session(engine) as session:
                all_accounts = session.exec(
                    select(Account).where(Account.role.in_(["listener", "support"]))
                ).all()

                if not all_accounts:
                    logger.warning("No listener accounts found!")
                    return

                # 按 id 取模做分片
                accounts = [a for a in all_accounts if a.id % shard_total == shard_index]
                logger.info(
                    f"Shard {shard_index}/{shard_total}: handling {len(accounts)}/{len(all_accounts)} accounts"
                )

                if not accounts:
                    logger.warning(f"Shard {shard_index} has no accounts, idling")

                for account in accounts:
                    try:
                        proxy = account.proxy
                        proxy_dict = get_proxy_dict(proxy) if proxy else None
                        api_id = account.api_id or 6
                        api_hash = account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e"

                        if not account.session_file_path:
                            logger.error(f"Account {account.phone_number} has no session file")
                            continue

                        sfp = account.session_file_path
                        if not os.path.exists(sfp):
                            logger.error(f"Session file not found: {sfp}")
                            continue

                        # 解密 session 文件到临时目录
                        try:
                            from app.core.encryption import is_session_encrypted, get_encryption_service
                            if is_session_encrypted(sfp):
                                enc = get_encryption_service()
                                decrypted = enc.decrypt_to_memory(sfp)
                                fname = os.path.basename(sfp)
                                dest = os.path.join(temp_workdir, fname)
                                with open(dest, "wb") as f:
                                    f.write(decrypted)
                                actual_path = dest
                            else:
                                actual_path = sfp
                        except Exception as dec_err:
                            logger.warning(f"Decrypt failed for {sfp}: {dec_err}, using raw file")
                            actual_path = sfp

                        # 若是 Telethon 格式，转换为 Pyrogram 格式
                        from app.services.session_converter import is_telethon_session, convert_telethon_to_pyrogram
                        if is_telethon_session(actual_path):
                            logger.info(f"Converting Telethon session → Pyrogram: {actual_path}")
                            if not convert_telethon_to_pyrogram(actual_path):
                                logger.error(f"Telethon conversion failed for {account.phone_number}, skipping")
                                continue

                        session_name = os.path.splitext(os.path.basename(actual_path))[0]
                        workdir = os.path.dirname(os.path.abspath(actual_path))

                        client = Client(
                            name=session_name,
                            workdir=workdir,
                            api_id=api_id,
                            api_hash=api_hash,
                            proxy=proxy_dict,
                            device_model=account.device_model,
                            system_version=account.system_version,
                            app_version=account.app_version,
                        )

                        client.add_handler(MessageHandler(self._handle_message))

                        self.clients.append(client)
                        self.client_accounts[session_name] = account
                        logger.info(f"Initialized client for {account.phone_number}")

                    except Exception as e:
                        logger.error(f"Failed to init client for {account.phone_number}: {e}")

            if not self.clients:
                logger.warning("No clients initialized; idling to avoid container restart loop")
                from pyrogram import idle
                await idle()
                return

            logger.info("Connecting clients...")
            # 逐个 start 以便连接后获取 Telegram user_id
            for c in self.clients:
                try:
                    await c.start()
                except Exception as e:
                    logger.error(f"Client start failed: {e}")

            # 收集我们自己账号的 Telegram user_id，避免 Director 自我回复
            for c in self.clients:
                try:
                    me = await c.get_me()
                    if me:
                        self._our_tg_ids.add(str(me.id))
                        logger.info(f"Listener account id={me.id} ({me.first_name}) registered")
                except Exception:
                    pass
            self.director.our_tg_ids = self._our_tg_ids
            logger.info(f"Director initialized, our_tg_ids={self._our_tg_ids}")

            # 保持运行，直到进程退出
            from pyrogram import idle
            await idle()

        finally:
            # 清理临时解密文件
            try:
                shutil.rmtree(temp_workdir)
            except Exception:
                pass
            # 关闭所有客户端
            for c in self.clients:
                try:
                    await c.stop()
                except Exception:
                    pass
