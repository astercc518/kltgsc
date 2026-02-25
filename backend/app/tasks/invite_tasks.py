"""
批量拉人 Celery 任务
"""
import logging
import asyncio
from celery.exceptions import SoftTimeLimitExceeded
from app.core.celery_app import celery_app
from app.core.db import get_session
from app.services.invite_service import InviteService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.invite_tasks.execute_invite_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=7200,
    time_limit=10800
)
def execute_invite_task(self, task_id: int):
    """
    执行拉人任务
    
    Args:
        task_id: 任务ID
    """
    logger.info(f"Starting invite task {task_id}")
    
    with next(get_session()) as session:
        invite_service = InviteService(session)
        
        try:
            # 运行异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                invite_service.execute_invite_task(task_id)
            )
            
            loop.close()
            
            logger.info(f"Invite task {task_id} completed: {result}")
            return result
            
        except SoftTimeLimitExceeded:
            logger.error(f"Invite task {task_id} timed out")
            return {"success": False, "error": "Task timed out", "status": "timeout"}
        except Exception as e:
            logger.error(f"Invite task {task_id} failed: {e}")

            # 重试
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e)

            return {"success": False, "error": str(e)}


@celery_app.task(name="app.tasks.invite_tasks.check_recurring_tasks", soft_time_limit=300, time_limit=600)
def check_recurring_tasks():
    """
    检查并触发循环任务（由 Celery Beat 调用）
    """
    from datetime import datetime, timedelta
    from sqlmodel import select
    from app.models.invite_task import InviteTask
    
    logger.info("Checking recurring invite tasks")
    
    with next(get_session()) as session:
        # 查找需要执行的循环任务
        now = datetime.utcnow()
        
        recurring_tasks = session.exec(
            select(InviteTask).where(
                InviteTask.is_recurring == True,
                InviteTask.status.in_(["completed", "pending"])
            )
        ).all()
        
        for task in recurring_tasks:
            # 检查是否到了下一次执行时间
            last_run = task.completed_at or task.created_at
            next_run = last_run + timedelta(hours=task.recurring_interval_hours)
            
            if now >= next_run:
                logger.info(f"Triggering recurring task {task.id}")
                
                # 重置任务状态
                task.status = "pending"
                task.success_count = 0
                task.fail_count = 0
                task.pending_count = 0
                task.started_at = None
                task.completed_at = None
                task.last_error = None
                
                session.add(task)
                session.commit()
                
                # 触发执行
                execute_invite_task.delay(task.id)
