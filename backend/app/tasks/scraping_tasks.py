"""
采集相关任务
- 批量加群
- 批量采集成员
"""
import random
import asyncio
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

from sqlmodel import Session as DBSession, select
from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.target_user import TargetUser
from app.models.scraping_task import ScrapingTask
from app.services.telegram_client import join_group_with_client, scrape_group_members

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def join_groups_batch_task(
    self,
    account_ids: List[int],
    group_links: List[str],
    scraping_task_id: int = None
):
    """
    批量加入群组
    """
    import time
    
    logger.info(f"Starting batch join: {len(account_ids)} accounts, {len(group_links)} groups")
    
    db_session = DBSession(engine)
    results = {
        "success": [],
        "failed": [],
        "total_accounts": len(account_ids),
        "total_groups": len(group_links)
    }
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # Get valid accounts
        accounts = []
        for aid in account_ids:
            account = db_session.get(Account, aid)
            if account and account.status == 'active':
                accounts.append(account)
        
        if not accounts:
            logger.warning("No valid accounts for batch join")
            _update_scraping_task_status(db_session, scraping_task_id, "failed", "No valid accounts", results)
            return results
        
        for group_link in group_links:
            for account in accounts:
                try:
                    logger.info(f"Account {account.phone_number} joining {group_link}")
                    
                    current_account = account
                    current_link = group_link
                    
                    async def do_join():
                        return await join_group_with_client(current_account, current_link, db_session=db_session)
                    
                    success, msg = loop.run_until_complete(do_join())
                    
                    if success or "already" in msg.lower():
                        results["success"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "message": msg
                        })
                    else:
                        results["failed"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "error": msg
                        })
                        
                except Exception as e:
                    error_str = str(e)
                    if "USER_ALREADY_PARTICIPANT" in error_str:
                        results["success"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "message": "已是成员"
                        })
                    else:
                        results["failed"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "error": error_str
                        })
                
                time.sleep(random.uniform(2, 5))
            
            time.sleep(random.uniform(3, 8))
        
        logger.info(f"Batch join completed: {len(results['success'])} success, {len(results['failed'])} failed")
        _update_scraping_task_status(db_session, scraping_task_id, "completed", None, results)
        
        return results
        
    except Exception as e:
        logger.error(f"Batch join task failed: {e}")
        _update_scraping_task_status(db_session, scraping_task_id, "failed", str(e), results)
        return {"error": str(e), **results}
    finally:
        db_session.close()


@celery_app.task(bind=True, max_retries=2)
def scrape_members_batch_task(
    self,
    account_ids: List[int],
    group_links: List[str],
    limit: int = 100,
    scraping_task_id: int = None,
    filter_config: dict = None
):
    """
    批量采集群成员
    """
    import time
    
    logger.info(f"Starting batch scrape: {len(account_ids)} accounts, {len(group_links)} groups, limit={limit}")
    
    db_session = DBSession(engine)
    results = {
        "success": [],
        "failed": [],
        "total_scraped": 0,
        "new_users": 0,
        "filter_config": filter_config
    }
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # Get valid accounts
        accounts = []
        for aid in account_ids:
            account = db_session.get(Account, aid)
            if account and account.status == 'active':
                accounts.append(account)
        
        if not accounts:
            logger.warning("No valid accounts for batch scrape")
            _update_scraping_task_status(db_session, scraping_task_id, "failed", "No valid accounts", results)
            return results

        # Round-robin account assignment
        for i, group_link in enumerate(group_links):
            account = accounts[i % len(accounts)]
            
            try:
                logger.info(f"Account {account.phone_number} scraping {group_link}")
                
                current_account = account
                current_link = group_link
                
                async def do_scrape():
                    return await scrape_group_members(
                        current_account, 
                        current_link, 
                        limit, 
                        db_session=db_session, 
                        filter_config=filter_config
                    )
                
                success, members = loop.run_until_complete(do_scrape())
                
                if success:
                    # Save scraped users
                    saved_count = 0
                    for m in members:
                        exists = db_session.exec(
                            select(TargetUser).where(TargetUser.telegram_id == m["telegram_id"])
                        ).first()
                        if not exists:
                            user = TargetUser(**m)
                            db_session.add(user)
                            saved_count += 1
                    
                    db_session.commit()
                    
                    results["success"].append({
                        "account": account.phone_number,
                        "group": group_link,
                        "count": len(members),
                        "new": saved_count
                    })
                    results["total_scraped"] += len(members)
                    results["new_users"] += saved_count
                    
                    logger.info(f"Scraped {len(members)} members from {group_link} (New: {saved_count})")
                else:
                    error_msg = members if isinstance(members, str) else "Unknown error"
                    results["failed"].append({
                        "account": account.phone_number,
                        "group": group_link,
                        "error": error_msg
                    })
                    
            except Exception as e:
                logger.error(f"Exception scraping {group_link}: {e}")
                results["failed"].append({
                    "account": account.phone_number,
                    "group": group_link,
                    "error": str(e)
                })
            
            time.sleep(random.uniform(5, 15))
            
        _update_scraping_task_status(db_session, scraping_task_id, "completed", None, results)
        logger.info(f"Batch scrape completed: {results['total_scraped']} scraped, {results['new_users']} new")
        return results
        
    except Exception as e:
        logger.error(f"Batch scrape task failed: {e}")
        _update_scraping_task_status(db_session, scraping_task_id, "failed", str(e), results)
        return {"error": str(e), **results}
    finally:
        db_session.close()


def _update_scraping_task_status(
    db_session: DBSession,
    task_id: Optional[int],
    status: str,
    error_message: Optional[str],
    results: dict
):
    """更新采集任务状态"""
    if not task_id:
        return
        
    try:
        task = db_session.get(ScrapingTask, task_id)
        if task:
            task.status = status
            task.success_count = results.get("total_scraped", len(results.get("success", [])))
            task.fail_count = len(results.get("failed", []))
            task.result_json = json.dumps(results)
            task.completed_at = datetime.utcnow()
            if error_message:
                task.error_message = error_message
            db_session.add(task)
            db_session.commit()
    except Exception as e:
        logger.error(f"Failed to update scraping task status: {e}")
