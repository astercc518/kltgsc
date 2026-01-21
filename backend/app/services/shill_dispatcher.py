import logging
import asyncio
import json
import random
from typing import List, Optional
from sqlmodel import Session, select
from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.keyword_monitor import KeywordMonitor, KeywordHit
from app.models.script import Script
from app.services.telegram_client import send_message_with_client, _create_client_and_run

logger = logging.getLogger(__name__)

class ShillDispatcher:
    def __init__(self):
        pass

    async def dispatch_shill(self, hit_id: int):
        """
        Main entry point to dispatch a shill response for a keyword hit
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

            if monitor.action_type != "trigger_script":
                logger.info(f"Monitor action is {monitor.action_type}, skipping shill dispatch")
                return
            
            if not monitor.reply_script_id:
                logger.warning(f"No reply script configured for monitor {monitor.id}")
                return
                
            script = session.get(Script, monitor.reply_script_id)
            if not script:
                logger.error(f"Script {monitor.reply_script_id} not found")
                return
                
            # 1. Select shill accounts (Tier 2)
            # Find accounts that are NOT the source user (obviously) and have tier='tier2'
            # Also ideally check if they are in the group, or can join.
            # For MVP, we pick accounts that are 'active' and 'tier2'.
            shill_accounts = session.exec(
                select(Account).where(
                    Account.tier == "tier2", 
                    Account.status == "active"
                )
            ).all()
            
            if not shill_accounts:
                logger.warning("No Tier 2 shill accounts available!")
                # Fallback to tier3 if needed, or abort
                return

            # 2. Parse script roles
            try:
                roles = json.loads(script.roles_json) # [{"name": "A", ...}, {"name": "B", ...}]
                lines = json.loads(script.lines_json) # [{"role": "A", "content": "...", "reply_to_line_index": ...}]
            except:
                logger.error("Invalid script JSON")
                return

            if not roles or not lines:
                return

            # 3. Assign accounts to roles
            # We need N unique accounts where N = len(roles)
            if len(shill_accounts) < len(roles):
                logger.warning(f"Not enough shill accounts. Need {len(roles)}, have {len(shill_accounts)}")
                return
                
            # Shuffle and pick
            selected_accounts = random.sample(shill_accounts, len(roles))
            role_map = {} # role_name -> Account
            
            for i, role in enumerate(roles):
                role_map[role['name']] = selected_accounts[i]
                
            logger.info(f"Assigned shill accounts for Hit {hit_id}: {role_map}")

            # 4. Execute script (Async)
            # We spin up a background task to run the conversation
            # We need to pass the hit info so the first message can reply to the user!
            
            # Since we are inside a Celery task or async context, we can launch another task 
            # or run inline if short. Conversations are long, so we should spawn a task.
            # But here we are in the dispatcher. Let's trigger a Celery task for the actual execution.
            
            celery_app.send_task(
                "app.worker.execute_shill_conversation",
                args=[hit.id, script.id, {k: v.id for k, v in role_map.items()}]
            )
            
            hit.status = "handling"
            session.add(hit)
            session.commit()


# --- Worker Task Implementation ---
# This usually goes into worker.py, but for modularity we can import it there.

async def run_shill_conversation(hit_id: int, script_id: int, role_account_ids: dict):
    """
    Executes the multi-turn conversation.
    role_account_ids: {"RoleA": 123, "RoleB": 456}
    """
    logger.info(f"Starting shill conversation for Hit {hit_id}")
    
    with Session(engine) as session:
        hit = session.get(KeywordHit, hit_id)
        script = session.get(Script, script_id)
        
        if not hit or not script:
            return

        lines = json.loads(script.lines_json)
        
        # Message ID tracking for replies
        # We need to map script line index to actual Telegram message ID
        # Special index -1 refers to the original user message
        message_id_map = { -1: int(hit.message_id) } 
        
        for i, line in enumerate(lines):
            role_name = line['role']
            content = line['content']
            reply_idx = line.get('reply_to_line_index')
            
            account_id = role_account_ids.get(role_name)
            if not account_id:
                continue
                
            account = session.get(Account, account_id)
            if not account:
                continue

            # Calculate random delay
            # First message should be fast (5-10s), subsequent ones slower (15-45s)
            if i == 0:
                delay = random.uniform(5, 12)
            else:
                delay = random.uniform(15, 45)
                
            logger.info(f"Shill: Waiting {delay:.1f}s...")
            await asyncio.sleep(delay)
            
            # Prepare reply_to_message_id
            reply_to_id = None
            if i == 0:
                # First line usually replies to the hit message
                reply_to_id = int(hit.message_id)
            elif reply_idx is not None:
                # Reply to a previous script line
                reply_to_id = message_id_map.get(reply_idx)
            
            # Send message
            # We need to join the group first if not joined? 
            # Assuming Tier 2 accounts are ALREADY in the group or can join.
            # Safe implementation: try join first (if public) or assume joined.
            # If hit.source_group_id is ID, we can't join by ID. Need link.
            # If we don't have link, we hope we are in.
            
            target = hit.source_group_id # This is ID
            # If we have a username, use that
            # Note: hit.source_group_id is string.
            
            success, result = await send_message_with_client_reply(
                account,
                target,
                content,
                reply_to_message_id=reply_to_id,
                db_session=session
            )
            
            if success:
                # result should be the message object or ID? 
                # Our send_message_with_client returns (bool, str). 
                # We need to modify it to return Message ID for threading!
                # For now, let's assume we update send_message to return ID in result string or change signature.
                # See update below.
                try:
                    # If we update send_message to return object or ID
                    msg_id = int(result) 
                    message_id_map[i] = msg_id
                except:
                    pass
            else:
                logger.error(f"Shill failed to send line {i}: {result}")
        
        hit.status = "handled"
        session.add(hit)
        session.commit()


async def send_message_with_client_reply(account: Account, chat_id: str, text: str, reply_to_message_id: Optional[int] = None, db_session: Session = None):
    """
    Enhanced send function that supports reply_to_message_id and returns message ID on success.
    """
    async def op(client, cid, txt, rid):
        try:
            # Try to convert chat_id to int if it looks like one
            try:
                target = int(cid)
            except:
                target = cid
                
            msg = await client.send_message(
                chat_id=target,
                text=txt,
                reply_to_message_id=rid
            )
            return msg.id
        except Exception as e:
            raise e
            
    try:
        success, res = await _create_client_and_run(account, op, chat_id, text, reply_to_message_id, db_session=db_session)
        return success, res
    except Exception as e:
        return False, str(e)
