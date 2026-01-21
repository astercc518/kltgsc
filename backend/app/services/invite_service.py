import logging
import asyncio
import random
from typing import List, Optional
from sqlmodel import Session, select
from app.models.account import Account
from app.models.target_user import TargetUser
from app.services.telegram_client import _create_client_and_run
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class InviteService:
    def __init__(self, session: Session):
        self.session = session

    async def invite_users_to_channel(self, account_id: int, channel_link: str, target_user_ids: List[int]) -> dict:
        """
        Invite a batch of users to a channel/group using a specific account.
        """
        account = self.session.get(Account, account_id)
        if not account:
            return {"success": False, "error": "Account not found"}

        # 1. Get target users
        targets = self.session.exec(select(TargetUser).where(TargetUser.id.in_(target_user_ids))).all()
        if not targets:
            return {"success": False, "error": "No valid targets found"}

        results = {
            "success": 0,
            "failed": 0,
            "errors": [],
            "flood_wait": 0
        }

        # 2. Define Pyrogram operation
        async def op(client, link, users):
            # Resolve channel
            try:
                chat = await client.get_chat(link)
            except Exception as e:
                return False, f"Failed to resolve channel {link}: {e}"

            success_count = 0
            fail_count = 0
            local_errors = []
            
            # Telegram usually allows adding multiple users at once, but for safety and error tracking
            # we might want to do it in small batches or one by one.
            # Adding multiple users in one call is safer against flood waits than many calls.
            # However, if one fails, the whole batch might fail or return partial results.
            # Let's try adding one by one for granular control and detailed error logging, 
            # but with delays.
            
            for user in users:
                user_identifier = user.username or user.telegram_id
                try:
                    # Random delay between invites
                    await asyncio.sleep(random.uniform(3, 8))
                    
                    await client.add_chat_members(chat_id=chat.id, user_ids=user_identifier)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    error_str = str(e)
                    local_errors.append(f"User {user_identifier}: {error_str}")
                    
                    if "FLOOD_WAIT" in error_str:
                         # Stop immediately on flood wait
                         raise e
                    if "USER_PRIVACY_RESTRICTED" in error_str:
                        # Common error, just skip
                        pass
            
            return True, {"success": success_count, "failed": fail_count, "errors": local_errors}

        # 3. Execute
        try:
            success, res = await _create_client_and_run(account, op, channel_link, targets, db_session=self.session)
            if success:
                # Update stats
                results["success"] = res["success"]
                results["failed"] = res["failed"]
                results["errors"] = res["errors"]
            else:
                results["failed"] = len(targets)
                results["errors"].append(res) # res is error string here
                
        except Exception as e:
            logger.error(f"Invite operation failed: {e}")
            results["failed"] = len(targets)
            results["errors"].append(str(e))
            if "FloodWait" in str(e):
                 results["flood_wait"] = 1 # Indicator
                 
        return results

    def check_daily_limit(self, account_id: int) -> bool:
        """
        Check if account has reached daily invite limit (e.g. 5-10 for safe accounts, 40-50 for disposable)
        TODO: Implement actual tracking using OperationLog or dedicated InviteLog
        For now, just return True (allow)
        """
        return True
