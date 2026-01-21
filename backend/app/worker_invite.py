import logging
import json
import asyncio
from sqlmodel import Session
from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.invite_task import InviteTask
from app.services.invite_service import InviteService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def execute_invite_task(self, task_id: int):
    """
    Execute an invite task
    Distributes targets among accounts and executes invites
    """
    logger.info(f"Starting Invite Task {task_id}")
    
    with Session(engine) as session:
        task = session.get(InviteTask, task_id)
        if not task:
            logger.error(f"Invite Task {task_id} not found")
            return

        task.status = "running"
        session.add(task)
        session.commit()
        
        try:
            account_ids = json.loads(task.account_ids_json)
            target_ids = json.loads(task.target_user_ids_json)
        except:
            task.status = "failed"
            session.add(task)
            session.commit()
            return

        if not account_ids or not target_ids:
            task.status = "completed" # Nothing to do
            session.add(task)
            session.commit()
            return

        service = InviteService(session)
        
        # Distribute targets to accounts
        # E.g. 100 targets, 10 accounts, limit 5 per account -> can only invite 50
        # For now, simple chunking
        
        chunk_size = task.max_invites_per_account
        
        # We need async loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        async def run_batch():
            current_target_idx = 0
            
            for acc_id in account_ids:
                if current_target_idx >= len(target_ids):
                    break
                    
                # Take next chunk of targets
                end_idx = min(current_target_idx + chunk_size, len(target_ids))
                batch_targets = target_ids[current_target_idx:end_idx]
                
                if not batch_targets:
                    break
                    
                logger.info(f"Account {acc_id} inviting {len(batch_targets)} users...")
                
                # Check daily limit? (Implemented in service, currently pass-through)
                
                # Execute invite
                result = await service.invite_users_to_channel(acc_id, task.target_channel, batch_targets)
                
                # Update stats
                task.success_count += result.get("success", 0)
                task.fail_count += result.get("failed", 0)
                session.add(task)
                session.commit()
                
                if result.get("flood_wait"):
                    logger.warning(f"Account {acc_id} hit flood wait, stopping usage of this account for now.")
                
                current_target_idx = end_idx
                
                # Global task delay between accounts to avoid spiking the channel add rate too much?
                await asyncio.sleep(2) 

        loop.run_until_complete(run_batch())
        
        task.status = "completed"
        session.add(task)
        session.commit()
        logger.info(f"Invite Task {task_id} completed")
