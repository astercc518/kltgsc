"""
监控相关任务
- 炒群对话
"""
import asyncio
import logging
from typing import Dict

from app.core.celery_app import celery_app
from app.services.shill_dispatcher import run_shill_conversation

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def execute_shill_conversation(self, hit_id: int, script_id: int, role_account_ids: Dict[str, int]):
    """
    执行炒群对话
    """
    logger.info(f"Starting shill conversation task for Hit {hit_id}")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        loop.run_until_complete(run_shill_conversation(hit_id, script_id, role_account_ids))
        return {"success": True, "hit_id": hit_id}
    except Exception as e:
        logger.error(f"Shill conversation failed: {e}")
        return {"success": False, "error": str(e)}
