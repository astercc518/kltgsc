import asyncio
import random
import logging
import json
from typing import List, Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.models.account import Account
from app.models.warmup_task import WarmupTask
from app.services.telegram_client import _create_client_and_run
from app.core.exceptions import AccountException
from pyrogram import Client, enums

logger = logging.getLogger(__name__)

# Safe channels to browse
DEFAULT_CHANNELS = [
    "telegram", "durov", "contest", "designers", "bloomberg",
    "bbcnews", "nytimes", "techcrunch", "androidchannel", "nasa"
]

class WarmupService:
    def __init__(self, session: Session):
        self.session = session
        
    async def run_task(self, task_id: int):
        task = self.session.get(WarmupTask, task_id)
        if not task:
            raise ValueError(f"WarmupTask {task_id} not found")
            
        task.status = "running"
        self.session.add(task)
        self.session.commit()
        
        account_ids = json.loads(task.account_ids_json)
        
        # Parse target channels - remove @ prefix if present
        channels = []
        if task.target_channels:
            for c in task.target_channels.split(","):
                c = c.strip()
                if c:
                    # Remove @ prefix if present
                    if c.startswith("@"):
                        c = c[1:]
                    channels.append(c)
        if not channels:
            channels = DEFAULT_CHANNELS
        
        logger.info(f"Target channels for warmup: {channels}")
            
        logger.info(f"Starting warmup task {task_id} for {len(account_ids)} accounts. Mode: {task.action_type}")
        
        # Run concurrently with semaphore limit
        tasks = []
        for aid in account_ids:
            tasks.append(self._warmup_account(aid, task, channels))
            
        sem = asyncio.Semaphore(5) 
        
        async def run_with_sem(coro):
            async def wrapped():
                async with sem:
                    return await coro
            return await wrapped()

        results = await asyncio.gather(*[run_with_sem(t) for t in tasks], return_exceptions=True)
        
        # Count success/fail
        success_count = 0
        fail_count = 0
        for r in results:
            if isinstance(r, Exception):
                fail_count += 1
                logger.error(f"Warmup account exception: {r}")
            elif r is True:
                success_count += 1
            else:
                fail_count += 1
                
        task.status = "completed"
        task.success_count = success_count
        task.fail_count = fail_count
        self.session.add(task)
        self.session.commit()
        logger.info(f"Warmup task {task_id} completed. Success: {success_count}, Fail: {fail_count}")

    async def _warmup_account(self, account_id: int, task: WarmupTask, channels: List[str]) -> bool:
        """返回 True 表示成功，False 表示失败"""
        account = self.session.get(Account, account_id)
        if not account:
            logger.warning(f"Account {account_id} not found, skipping")
            return False

        # Check if account is usable
        if account.status in ["banned"]:
            logger.warning(f"Account {account.phone_number} is banned, skipping")
            return False
        if account.cooldown_until and account.cooldown_until > datetime.utcnow():
            logger.warning(f"Account {account.phone_number} in cooldown, skipping")
            return False

        end_time = datetime.utcnow() + timedelta(minutes=task.duration_minutes)

        try:
            async def operation(client: Client):
                logger.info(f"Account {account.phone_number} started warmup")

                # 检测 Search Ban：尝试解析官方账号 @Telegram
                is_search_banned = False
                try:
                    await client.get_users("Telegram")
                except Exception as search_test_err:
                    error_str = str(search_test_err)
                    if "USERNAME_NOT_OCCUPIED" in error_str or "USERNAME_INVALID" in error_str:
                        is_search_banned = True
                        logger.warning(f"Account {account.phone_number} is Search Banned")
                        account.status = "spam_block"
                        self.session.add(account)
                        self.session.commit()

                # 获取账号已加入的对话列表
                existing_dialogs = []
                try:
                    async for dialog in client.get_dialogs(limit=50):
                        if dialog.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
                            existing_dialogs.append(dialog.chat.id)
                    logger.info(f"Account {account.phone_number} has {len(existing_dialogs)} group/channel dialogs")
                except Exception as e:
                    logger.warning(f"Error getting dialogs: {e}")

                warmup_targets = existing_dialogs.copy()

                # 尝试加入目标频道
                logger.info(f"Account {account.phone_number} trying to join channels: {channels}")
                for ch in channels:
                    try:
                        chat_identifier = ch

                        if ch.startswith("https://t.me/") or ch.startswith("http://t.me/"):
                            if "/+" in ch or "/joinchat/" in ch:
                                chat_identifier = ch
                            else:
                                chat_identifier = ch.split("/")[-1]
                        elif ch.startswith("t.me/"):
                            chat_identifier = ch.replace("t.me/", "")

                        logger.info(f"Account {account.phone_number} joining with identifier: {chat_identifier}")
                        joined_chat = await client.join_chat(chat_identifier)
                        if joined_chat.id not in warmup_targets:
                            warmup_targets.append(joined_chat.id)
                            logger.info(f"Account {account.phone_number} joined {ch}")
                    except Exception as e:
                        error_str = str(e)
                        logger.warning(f"Account {account.phone_number} failed to join {ch}: {error_str}")
                        if "USER_ALREADY_PARTICIPANT" in error_str or "INVITE_REQUEST_SENT" in error_str:
                            try:
                                chat = await client.get_chat(chat_identifier)
                                if chat.id not in warmup_targets:
                                    warmup_targets.append(chat.id)
                                    logger.info(f"Account {account.phone_number} already in {ch}")
                            except Exception as get_err:
                                logger.warning(f"Account {account.phone_number} failed to get chat {ch}: {get_err}")

                if not warmup_targets:
                    if is_search_banned:
                        logger.warning(f"Account {account.phone_number} is Search Banned and has no existing dialogs")
                    else:
                        logger.warning(f"Account {account.phone_number} has no dialogs for warmup")
                    return "no_targets"

                logger.info(f"Account {account.phone_number} warmup targets: {len(warmup_targets)} chats")

                while datetime.utcnow() < end_time:
                    delay = random.randint(task.min_delay, task.max_delay)
                    await asyncio.sleep(delay)

                    action = task.action_type
                    if action == "mixed":
                        action = random.choice(["view_channel", "view_channel", "reaction"])

                    try:
                        target_chat_id = random.choice(warmup_targets)

                        if action == "view_channel":
                            try:
                                msg_count = 0
                                async for msg in client.get_chat_history(target_chat_id, limit=random.randint(2, 5)):
                                    await asyncio.sleep(random.uniform(1, 3))
                                    try:
                                        await client.read_chat_history(target_chat_id, msg.id)
                                    except Exception:
                                        pass
                                    msg_count += 1
                                if msg_count > 0:
                                    logger.info(f"Account {account.phone_number} read {msg_count} messages")
                            except Exception as e:
                                logger.warning(f"Error reading history: {e}")

                        elif action == "reaction":
                            try:
                                history = []
                                async for msg in client.get_chat_history(target_chat_id, limit=10):
                                    history.append(msg)

                                if history:
                                    msg = random.choice(history)
                                    try:
                                        await client.send_reaction(chat_id=target_chat_id, message_id=msg.id, emoji="👍")
                                        logger.info(f"Account {account.phone_number} reacted to message")
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                    except Exception as e:
                        logger.warning(f"Warmup step error for {account.phone_number}: {e}")

                logger.info(f"Account {account.phone_number} finished warmup")
                return "done"

            success, result = await _create_client_and_run(account, operation, db_session=self.session)

            if success:
                account.last_active = datetime.utcnow()
                self.session.add(account)
                self.session.commit()
                return result != "no_targets"
            else:
                logger.warning(f"Account {account.phone_number} warmup failed: {result}")
                return False

        except AccountException as e:
            logger.warning(f"Account {account.phone_number} exception during warmup: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error for {account.phone_number}: {e}")
            return False
