"""
监控相关任务
- 炒群对话（静态剧本 / Director-Actor AI 模式）
"""
import re
import asyncio
import logging
from typing import Dict, List, Optional

from celery.exceptions import SoftTimeLimitExceeded
from pyrogram.enums import ChatAction
from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.account import Account
from app.services.shill_dispatcher import run_shill_conversation
from app.services.telegram_client import _create_client_and_run

logger = logging.getLogger(__name__)

# Shared with shill_dispatcher — duplicated here to avoid circular import
_HALLUCINATION_RE = re.compile(
    r'(作为.{0,4}AI|我是.{0,4}(AI|助手|语言模型)|'
    r'无法提供|对不起，我|抱歉，我|我无法|我没有能力|'
    r'请注意我是|根据我的训练|as an AI)',
    re.IGNORECASE,
)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=3600, time_limit=7200)
def execute_shill_conversation(self, hit_id: int, script_id: int, role_account_ids: Dict[str, int]):
    """
    执行静态剧本炒群对话（原有逻辑，保持兼容）
    """
    logger.info(f"Starting shill conversation task for Hit {hit_id}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run_shill_conversation(hit_id, script_id, role_account_ids))
        return {"success": True, "hit_id": hit_id}
    except SoftTimeLimitExceeded:
        logger.error(f"Shill conversation timed out for Hit {hit_id}")
        return {"success": False, "error": "Task timed out", "hit_id": hit_id}
    except Exception as e:
        logger.error(f"Shill conversation failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=120,
    time_limit=180,
    queue="high_priority",
)
def execute_single_shill_line(
    self,
    account_id: int,
    chat_id: str,
    text: str,
    reply_to_message_id: Optional[int] = None,
):
    """
    Director-Actor 模式的单条消息发送任务。

    流程：
    1. 最终 anti-hallucination 守门（防止调度层漏过的内容下发）
    2. 发送 ChatAction.TYPING，持续 len(text) * 0.2 秒（上限 10s）
    3. 真正 send_message
    """
    if _HALLUCINATION_RE.search(text or ""):
        logger.warning(
            f"execute_single_shill_line: hallucination detected, aborting. "
            f"account={account_id} preview={text[:60]!r}"
        )
        return {"success": False, "error": "hallucination_filtered"}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        with Session(engine) as session:
            account = session.get(Account, account_id)
            if not account:
                return False, "account_not_found"

            async def op(client):
                # Normalize chat_id to int when possible (numeric group IDs)
                try:
                    target = int(chat_id)
                except (ValueError, TypeError):
                    target = chat_id

                # 预热 peers 缓存：新建的临时 session peers 表为空，
                # send_message 按 chat_id 查找会报 "Peer id invalid"。
                # get_dialogs 是 async generator，需要 async for 消费才能填充 peers 表。
                try:
                    async for _ in client.get_dialogs(limit=50):
                        pass
                except Exception:
                    pass

                typing_secs = min(len(text) * 0.2, 10.0)
                await client.send_chat_action(chat_id=target, action=ChatAction.TYPING)
                await asyncio.sleep(typing_secs)

                msg = await client.send_message(
                    chat_id=target,
                    text=text,
                    reply_to_message_id=reply_to_message_id,
                )
                return msg.id

            return await _create_client_and_run(account, op, db_session=session)

    try:
        success, result = loop.run_until_complete(_run())
        logger.info(
            f"execute_single_shill_line: account={account_id} "
            f"success={success} result={result}"
        )
        return {"success": success, "result": str(result) if success else result}
    except SoftTimeLimitExceeded:
        logger.error(f"execute_single_shill_line timed out: account={account_id}")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        logger.error(f"execute_single_shill_line failed: account={account_id} err={e}")
        return {"success": False, "error": str(e)}
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600, time_limit=900)
def execute_free_conversation(
    self,
    account_ids: List[int],
    chat_id: str,
    topic: str,
    turns_per_account: int = 1,
):
    """
    多账号自由发言任务：为每个账号用其 AI 人设生成消息，按随机间隔调度发送。
    本任务仅负责生成内容 + 调度，实际发送由 execute_single_shill_line 完成。
    """
    logger.info(
        f"execute_free_conversation: accounts={account_ids} "
        f"chat={chat_id} topic={topic!r} turns={turns_per_account}"
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        from app.services.shill_dispatcher import dispatch_free_conversation
        scheduled_count, total_seconds = loop.run_until_complete(
            dispatch_free_conversation(account_ids, chat_id, topic, turns_per_account)
        )
        logger.info(
            f"execute_free_conversation: {scheduled_count} messages scheduled "
            f"over ~{total_seconds}s"
        )
        return {
            "success": True,
            "scheduled_count": scheduled_count,
            "scheduled_duration_seconds": total_seconds,
        }
    except SoftTimeLimitExceeded:
        logger.error("execute_free_conversation timed out during scheduling")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        logger.error(f"execute_free_conversation failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        loop.close()
        asyncio.set_event_loop(None)
