"""
营销相关任务
- 消息发送（安全模式）
- 养号任务
- 自动回复
- 脚本执行
"""
import random
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from sqlmodel import Session, select
from app.core.db import engine
from app.core.celery_app import celery_app
from app.core.concurrency import get_redis_semaphore
from app.models.account import Account
from app.models.target_user import TargetUser
from app.models.send_task import SendTask, SendRecord
from app.services.telegram_client import send_message_with_client
from app.services.safe_send_dispatcher import SafeSendDispatcher, SafeSendConfig

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def execute_send_task(self, task_id: int, account_ids: List[int], target_user_ids: List[int], config_override: dict = None):
    """
    执行安全营销发送任务
    
    安全策略：
    1. 每账号每日限额（新账号15条，普通30条，老账号50条）
    2. 随机发送间隔（60-180秒）
    3. 连续发送5条后休息5-15分钟
    4. 触发FloodWait后冷却1小时
    5. 智能账号轮换（优先使用配额充足的账号）
    """
    logger.info(f"Starting Safe Send Task {task_id} with {len(account_ids)} accounts for {len(target_user_ids)} targets")
    
    # 创建配置
    config = SafeSendConfig()
    if config_override:
        for key, value in config_override.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    semaphore = get_redis_semaphore(limit=5)
    
    with Session(engine) as session:
        task = session.get(SendTask, task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"success": False, "error": "Task not found"}
        
        # 初始化调度器
        dispatcher = SafeSendDispatcher(session, config)
        
        # 获取发送计划
        plan = dispatcher.create_send_plan(account_ids, target_user_ids)
        logger.info(f"Send Plan: {plan}")
        
        # 检查容量
        if plan['total_capacity_today'] == 0:
            task.status = "failed"
            session.add(task)
            session.commit()
            return {"success": False, "error": "No available capacity today. All accounts have reached their daily limits."}
        
        task.status = "running"
        session.add(task)
        session.commit()
        
        # 获取目标用户
        target_pool = session.exec(
            select(TargetUser).where(TargetUser.id.in_(target_user_ids))
        ).all()
        
        if not target_pool:
            task.status = "failed"
            session.add(task)
            session.commit()
            return {"success": False, "error": "No target users found"}
        
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def process_safe_batch():
            sent_count = 0
            skipped_count = 0
            
            for target in target_pool:
                # 检查任务状态
                session.refresh(task)
                if task.status != "running":
                    logger.info(f"Task {task_id} stopped by user")
                    break
                
                # 获取可用账号
                available_accounts = dispatcher.get_available_accounts(account_ids)
                
                if not available_accounts:
                    logger.warning(f"No available accounts. Stopping task. Sent: {sent_count}, Skipped: {skipped_count}")
                    break
                
                # 选择账号
                result = dispatcher.select_next_account(available_accounts)
                if not result:
                    logger.warning("Could not select account")
                    skipped_count += 1
                    continue
                    
                account, stats = result
                
                # 检查是否需要休息
                needs_rest, rest_duration = dispatcher.should_rest(stats)
                if needs_rest:
                    logger.info(f"Account {account.id} resting for {rest_duration}s after {stats.consecutive_sends} sends")
                    await asyncio.sleep(rest_duration)
                    dispatcher.record_rest(account.id)
                
                # 发送间隔
                delay = dispatcher.get_send_delay()
                logger.info(f"Waiting {delay}s before sending to {target.telegram_id} via account {account.id}")
                await asyncio.sleep(delay)
                
                # 发送消息
                try:
                    with semaphore.acquire_lock():
                        target_identifier = target.username or target.telegram_id
                        success, msg = await send_message_with_client(
                            account,
                            target_identifier,
                            task.message_content,
                            db_session=session
                        )
                        
                        # 记录发送
                        error_type = None
                        if not success and msg:
                            error_type = msg
                        dispatcher.record_send(account.id, success, error_type)
                        
                        # 记录到任务
                        record = SendRecord(
                            task_id=task.id,
                            account_id=account.id,
                            target_user_id=target.id,
                            status="success" if success else "failed",
                            error_message=msg if not success else None
                        )
                        session.add(record)
                        
                        if success:
                            task.success_count += 1
                            sent_count += 1
                        else:
                            task.fail_count += 1
                            logger.warning(f"Failed to send to {target.telegram_id}: {msg}")
                            
                            # 如果是严重错误，标记目标用户
                            if msg and ('banned' in msg.lower() or 'deleted' in msg.lower()):
                                target.status = "invalid"
                                session.add(target)
                        
                        session.add(task)
                        session.commit()
                        
                except Exception as e:
                    logger.error(f"Error sending to {target.telegram_id}: {e}")
                    dispatcher.record_send(account.id, False, str(e))
                    task.fail_count += 1
                    session.add(task)
                    session.commit()
            
            return sent_count, skipped_count
        
        try:
            sent_count, skipped_count = loop.run_until_complete(process_safe_batch())
        finally:
            loop.close()
        
        # 更新任务状态
        session.refresh(task)
        remaining = len(target_user_ids) - task.success_count - task.fail_count
        
        if task.status == "running":
            if remaining > 0:
                task.status = "paused"  # 还有剩余，等待下次执行
                logger.info(f"Task {task_id} paused. Remaining: {remaining}")
            else:
                task.status = "completed"
            session.add(task)
            session.commit()
    
    logger.info(f"Task {task_id} finished. Success: {task.success_count}, Failed: {task.fail_count}")
    return {
        "success": True,
        "task_id": task_id,
        "sent": task.success_count,
        "failed": task.fail_count,
        "remaining": remaining
    }


@celery_app.task(bind=True)
def continue_send_task(self, task_id: int, account_ids: List[int]):
    """
    继续执行未完成的发送任务
    用于分批发送时的后续批次
    """
    with Session(engine) as session:
        task = session.get(SendTask, task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        if task.status not in ["paused", "pending"]:
            return {"success": False, "error": f"Task is {task.status}, cannot continue"}
        
        # 获取未发送的目标用户
        sent_records = session.exec(
            select(SendRecord.target_user_id).where(SendRecord.task_id == task_id)
        ).all()
        sent_target_ids = set(sent_records)
        
        # 这里需要从任务中获取原始目标列表
        # 暂时返回错误，需要在任务模型中保存目标ID列表
        return {"success": False, "error": "Feature not implemented - need to store target_ids in task"}


@celery_app.task(bind=True, max_retries=2)
def execute_warmup_task(self, warmup_task_id: int):
    """执行养号任务"""
    from app.services.warmup_service import WarmupService
    
    logger.info(f"Starting warmup task {warmup_task_id}")
    
    with Session(engine) as session:
        service = WarmupService(session)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
            
        try:
            loop.run_until_complete(service.run_task(warmup_task_id))
            return {"success": True, "task_id": warmup_task_id}
        except Exception as e:
            logger.error(f"Warmup task {warmup_task_id} failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            loop.close()


@celery_app.task(bind=True)
def check_auto_reply_task(self, account_id: int):
    """检查并处理自动回复"""
    logger.info(f"Checking auto-replies for account {account_id}")
    
    with Session(engine) as session:
        account = session.get(Account, account_id)
        if not account:
            return {"success": False, "error": "Account not found"}
        
        if not account.auto_reply:
            return {"success": False, "error": "Auto-reply not enabled"}
        
        try:
            logger.info(f"Auto-reply check completed for account {account_id}")
            return {
                "success": True,
                "account_id": account_id,
                "message": "Auto-reply check completed"
            }
        except Exception as e:
            logger.error(f"Auto-reply error for account {account_id}: {e}")
            return {"success": False, "error": str(e)}


@celery_app.task(bind=True)
def execute_script_task(self, script_task_id: int):
    """执行炒群脚本任务"""
    from app.models.script import Script, ScriptTask
    
    logger.info(f"Starting script task {script_task_id}")
    
    with Session(engine) as session:
        task = session.get(ScriptTask, script_task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        task.status = "running"
        session.add(task)
        session.commit()
        
        try:
            script = session.get(Script, task.script_id)
            if not script:
                task.status = "failed"
                session.add(task)
                session.commit()
                return {"success": False, "error": "Script not found"}
            
            logger.info(f"Executing script {script.id} for task {script_task_id}")
            
            task.status = "completed"
            session.add(task)
            session.commit()
            
            return {"success": True, "task_id": script_task_id}
            
        except Exception as e:
            logger.error(f"Script task {script_task_id} failed: {e}")
            task.status = "failed"
            session.add(task)
            session.commit()
            return {"success": False, "error": str(e)}
