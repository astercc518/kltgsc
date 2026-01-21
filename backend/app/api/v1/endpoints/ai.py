from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List
from app.core.db import get_session
from app.services.llm import LLMService
from app.models.account import Account
from app.worker import check_auto_reply_task

router = APIRouter()

@router.get("/test_connection")
async def test_ai_connection(
    session: Session = Depends(get_session)
):
    """测试 LLM 连接"""
    llm = LLMService(session)
    success = await llm.test_connection()
    if not success:
        return {"status": "failed", "message": "Connection failed"}
    return {"status": "success", "message": "Connection successful"}

@router.post("/trigger_auto_reply")
async def trigger_auto_reply(
    account_ids: List[int] = Query(None),
    session: Session = Depends(get_session)
):
    """手动触发账号的自动回复检查"""
    if not account_ids:
        # If no IDs provided, check all active accounts with auto_reply enabled
        accounts = session.exec(
            select(Account)
            .where(Account.status == "active")
            .where(Account.auto_reply == True)
        ).all()
        account_ids = [a.id for a in accounts]
    
    if not account_ids:
        return {"message": "No accounts found for auto-reply check", "task_ids": []}
        
    task_ids = []
    for aid in account_ids:
        task = check_auto_reply_task.delay(aid)
        task_ids.append(task.id)
        
    return {
        "message": f"Triggered check for {len(task_ids)} accounts", 
        "task_ids": task_ids
    }
