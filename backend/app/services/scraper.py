import logging
from typing import List, Tuple, Optional
from datetime import datetime
from sqlmodel import Session, select

from app.models.account import Account
from app.models.target_user import TargetUser
from app.services.telegram_client import _create_client_and_run

logger = logging.getLogger(__name__)

async def join_group(account_id: int, group_link: str, session: Session) -> Tuple[bool, str]:
    """使用指定账号加入群组"""
    account = session.get(Account, account_id)
    if not account:
        return False, "Account not found"

    async def op(client, link):
        try:
            chat = await client.join_chat(link)
            return f"Joined {chat.title}"
        except Exception as e:
            if "USER_ALREADY_PARTICIPANT" in str(e):
                return "Already joined"
            raise e

    return await _create_client_and_run(account, op, group_link)

async def scrape_members(account_id: int, group_link: str, limit: int, session: Session) -> Tuple[bool, str, int]:
    """采集群成员"""
    account = session.get(Account, account_id)
    if not account:
        return False, "Account not found", 0

    scraped_count = 0
    new_count = 0

    async def op(client, link, max_count):
        nonlocal scraped_count, new_count
        try:
            chat = await client.get_chat(link)
            # Iterate through members
            # Note: client.get_chat_members is an async generator
            async for member in client.get_chat_members(chat.id, limit=max_count):
                user = member.user
                if user.is_bot or user.is_deleted:
                    continue
                
                # Check duplication
                existing = session.exec(select(TargetUser).where(TargetUser.user_id == user.id)).first()
                if not existing:
                    target = TargetUser(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        phone=user.phone_number,
                        source_group=link,
                        status="new",
                        scraped_at=datetime.utcnow()
                    )
                    session.add(target)
                    new_count += 1
                
                scraped_count += 1
            
            session.commit()
            return f"Scraped {scraped_count} members"
        except Exception as e:
            raise e

    success, msg = await _create_client_and_run(account, op, group_link, limit)
    return success, msg, new_count
