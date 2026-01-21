from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.send_task import SendTask, SendTaskCreate, SendTaskRead
from app.models.account import Account
from app.worker import execute_send_task
from app.services.permission_service import PermissionService

router = APIRouter()

@router.post("/tasks", response_model=SendTaskRead)
def create_send_task(
    task: SendTaskCreate,
    session: Session = Depends(get_session)
):
    """创建并启动发送任务"""
    
    # --- Permission Check ---
    accounts = session.exec(select(Account).where(Account.id.in_(task.account_ids))).all()
    valid_accounts = PermissionService.filter_accounts_for_action(accounts, "mass_dm")
    
    if len(valid_accounts) < len(task.account_ids):
        # Some accounts were filtered out
        invalid_count = len(task.account_ids) - len(valid_accounts)
        if len(valid_accounts) == 0:
            raise HTTPException(status_code=400, detail="Selected accounts are not allowed to perform Mass DM (Tier Restriction)")
        # Optionally warn user or just proceed with valid ones
        # For API simplicity, we proceed with valid ones but could return warning
        pass
        
    valid_account_ids = [acc.id for acc in valid_accounts]
    
    # 1. Create Task Record
    db_task = SendTask(
        name=task.name,
        message_content=task.message_content,
        min_delay=task.min_delay,
        max_delay=task.max_delay,
        total_count=len(task.target_user_ids)
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # 2. Trigger Celery Task
    # Pass necessary IDs to the worker
    execute_send_task.delay(
        task_id=db_task.id,
        account_ids=valid_account_ids,
        target_user_ids=task.target_user_ids
    )
    
    return db_task

@router.get("/tasks", response_model=List[SendTaskRead])
def get_send_tasks(
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """获取任务列表"""
    query = select(SendTask).offset(skip).limit(limit).order_by(SendTask.created_at.desc())
    return session.exec(query).all()
