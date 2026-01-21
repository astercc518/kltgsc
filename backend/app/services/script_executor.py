import asyncio
import random
import json
import logging
from datetime import datetime
from sqlmodel import Session
from app.models.script import ScriptTask, Script
from app.models.account import Account
from app.services.telegram_client import send_message_with_client

logger = logging.getLogger(__name__)

class ScriptExecutorService:
    def __init__(self, db_session: Session):
        self.session = db_session

    async def execute_task(self, task_id: int):
        """
        Execute a script task (coordinate multiple accounts)
        """
        task = self.session.get(ScriptTask, task_id)
        if not task:
            logger.error(f"ScriptTask {task_id} not found")
            return

        script = self.session.get(Script, task.script_id)
        if not script or not script.lines_json:
            logger.error("Script not ready or not found")
            return

        task.status = "running"
        self.session.add(task)
        self.session.commit()

        lines = json.loads(script.lines_json)
        account_map = json.loads(task.account_mapping_json) # role_name -> account_id
        
        # Resume from current step
        start_index = task.current_step
        
        try:
            for i in range(start_index, len(lines)):
                line = lines[i]
                role = line["role"]
                content = line["content"]
                
                account_id = account_map.get(role)
                if not account_id:
                    logger.warning(f"No account mapped for role {role}, skipping line")
                    continue
                    
                account = self.session.get(Account, account_id)
                if not account:
                    logger.warning(f"Account {account_id} not found, skipping")
                    continue

                # 1. Delay
                delay = random.uniform(task.min_delay, task.max_delay)
                logger.info(f"Task {task_id}: Waiting {delay:.1f}s before sending...")
                await asyncio.sleep(delay)
                
                # 2. Send Message
                logger.info(f"Task {task_id}: Role {role} sending: {content}")
                try:
                    success, msg = await send_message_with_client(account, task.target_group, content, db_session=self.session)
                    if not success:
                        logger.error(f"Task {task_id}: Failed to send: {msg}")
                        # Optionally pause or retry? For now continue
                except Exception as e:
                    logger.error(f"Task {task_id}: Error sending: {e}")
                
                # 3. Update Progress
                task.current_step = i + 1
                self.session.add(task)
                self.session.commit()
                
            task.status = "completed"
            self.session.add(task)
            self.session.commit()
            logger.info(f"ScriptTask {task_id} completed")
            
        except Exception as e:
            logger.error(f"ScriptTask {task_id} failed: {e}")
            task.status = "failed"
            self.session.add(task)
            self.session.commit()
