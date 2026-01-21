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
        
        # 上下文缓存: key = chat_id, value = List of recent messages
        self.context_cache: Dict[int, List[str]] = {}
        self.context_max_size = 10  # 每个群缓存最近10条消息

    async def _handle_message(self, client: Client, message):
        """
        消息处理核心逻辑 - 支持被动式(两级过滤)和主动式营销
        """
        if not message.text:
            return
        
        # 缓存上下文消息
        chat_id = message.chat.id
        if chat_id not in self.context_cache:
            self.context_cache[chat_id] = []
        self.context_cache[chat_id].append(message.text)
        if len(self.context_cache[chat_id]) > self.context_max_size:
            self.context_cache[chat_id].pop(0)

        with Session(engine) as session:
            active_monitors = session.exec(
                select(KeywordMonitor).where(KeywordMonitor.is_active == True)
            ).all()
            
            chat_title = message.chat.title or str(chat_id)
            user_id = message.from_user.id if message.from_user else 0
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
            except:
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
            except:
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
        熔断机制检查：防止单规则回复过多
        """
        today = date.today().isoformat()
        
        # 检查是否需要重置计数
        if monitor.last_reply_date != today:
            monitor.daily_reply_count = 0
            monitor.last_reply_date = today
        
        # 检查是否超限
        max_replies = monitor.max_replies_per_day or 10
        if monitor.daily_reply_count >= max_replies:
            return False
        
        # 增加计数
        monitor.daily_reply_count += 1
        session.add(monitor)
        session.commit()
        
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
        
        # 3. 触发剧本 (被动模式下通常不主动回复，但可以触发后台任务)
        if monitor.action_type == "trigger_script" and monitor.reply_script_id:
            from app.services.shill_dispatcher import ShillDispatcher
            dispatcher = ShillDispatcher()
            await dispatcher.dispatch_shill(hit.id)

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
        
        # 2. 选择回复账号 (TODO: 账号轮询，当前使用监听账号)
        reply_client = client
        # if monitor.enable_account_rotation:
        #     reply_client = self._select_reply_account(message.chat.id)
        
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
        """根据 AI 人设生成回复"""
        try:
            from app.services.llm import LLMService
            llm = LLMService(session)
            
            # 获取人设 Prompt
            persona = monitor.ai_persona or "helpful"
            if persona == "custom" and monitor.ai_reply_prompt:
                system_prompt = monitor.ai_reply_prompt
            else:
                system_prompt = AI_PERSONA_PROMPTS.get(persona, AI_PERSONA_PROMPTS["helpful"])
            
            # 获取上下文
            chat_id = message.chat.id
            context = self.context_cache.get(chat_id, [])[-5:]
            context_str = "\n".join(context) if context else ""
            
            user_prompt = f"""
群聊上下文:
{context_str}

最新消息 (需要回复): {message.text}

请根据人设，生成一条自然的群聊回复。要求：
1. 简短，不超过2句话
2. 口语化，像真人聊天
3. 不要带链接或广告词
4. 可以适当有错别字或表情
"""
            
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
        logger.info("Starting Listener Service...")
        
        with Session(engine) as session:
            accounts = session.exec(
                select(Account).where(Account.role.in_(["listener", "support"]))
            ).all()
            
            if not accounts:
                logger.warning("No listener accounts found!")
                return

            logger.info(f"Found {len(accounts)} listener accounts")

            for account in accounts:
                try:
                    proxy = account.proxy
                    proxy_dict = get_proxy_dict(proxy) if proxy else None
                    api_id = account.api_id or 6
                    api_hash = account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e"
                    
                    if not account.session_file_path:
                        logger.error(f"Account {account.phone_number} has no session file")
                        continue
                        
                    session_name = account.session_file_path.split("/")[-1].replace(".session", "")
                    
                    client = Client(
                        name=session_name,
                        workdir="sessions",
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
            logger.warning("No clients initialized")
            return

        logger.info("Connecting clients...")
        from pyrogram import compose
        await compose(self.clients)
