"""
自动化工作流 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from pydantic import BaseModel

from app.core.db import get_session
from app.models.account import Account
from app.services.workflow_engine import (
    WorkflowEngine, 
    COMBAT_ROLE_PERMISSIONS,
    ActionType
)

router = APIRouter()


class AccountPermissionCheck(BaseModel):
    account_id: int
    action: str  # scrape, send_dm, invite_group, ai_reply


@router.get("/roles/config")
def get_role_config():
    """获取战斗角色权限配置"""
    return COMBAT_ROLE_PERMISSIONS


@router.get("/roles/stats")
def get_role_stats(
    session: Session = Depends(get_session)
):
    """获取各角色账号统计"""
    engine = WorkflowEngine(session)
    return engine.get_role_stats()


@router.post("/check-permission")
def check_account_permission(
    request: AccountPermissionCheck,
    session: Session = Depends(get_session)
):
    """检查账号是否有权限执行指定操作"""
    account = session.get(Account, request.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        action_type = ActionType(request.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
    
    engine = WorkflowEngine(session)
    result = engine.check_account_permission(account, action_type)
    return result


@router.post("/select-account")
def select_account_for_action(
    action: str = Query(..., description="操作类型: scrape, send_dm, invite_group, ai_reply"),
    target_score: Optional[int] = Query(None, description="目标用户评分"),
    exclude_ids: Optional[str] = Query(None, description="排除的账号ID，逗号分隔"),
    session: Session = Depends(get_session)
):
    """为指定操作智能选择账号"""
    try:
        action_type = ActionType(action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    exclude_list = []
    if exclude_ids:
        exclude_list = [int(x.strip()) for x in exclude_ids.split(",") if x.strip()]
    
    engine = WorkflowEngine(session)
    account = engine.select_account_for_action(
        action_type=action_type,
        target_score=target_score,
        exclude_ids=exclude_list
    )
    
    if not account:
        return {"account": None, "message": "没有可用的账号"}
    
    return {
        "account": {
            "id": account.id,
            "phone_number": account.phone_number,
            "combat_role": account.combat_role,
            "health_score": account.health_score,
            "daily_action_count": account.daily_action_count
        }
    }


@router.post("/execute/scrape-and-reach")
async def execute_scrape_and_reach(
    source_group_id: int = Query(...),
    campaign_id: Optional[int] = Query(None),
    session: Session = Depends(get_session)
):
    """执行采集触达工作流"""
    engine = WorkflowEngine(session)
    result = await engine.execute_scrape_and_reach_workflow(
        source_group_id=source_group_id,
        campaign_id=campaign_id
    )
    return result


@router.post("/reset-daily-counts")
def reset_daily_action_counts(
    session: Session = Depends(get_session)
):
    """重置所有账号的每日操作计数（定时任务调用）"""
    accounts = session.exec(select(Account)).all()
    count = 0
    for account in accounts:
        if account.daily_action_count and account.daily_action_count > 0:
            account.daily_action_count = 0
            session.add(account)
            count += 1
    
    session.commit()
    return {"reset_count": count, "message": f"已重置 {count} 个账号的每日计数"}
