from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.invite_task import InviteTask, InviteTaskCreate, InviteTaskRead
from app.models.account import Account
from app.core.celery_app import celery_app
from app.services.permission_service import PermissionService
import json

router = APIRouter()

@router.post("/tasks", response_model=InviteTaskRead)
def create_invite_task(
    task_create: InviteTaskCreate,
    session: Session = Depends(get_session)
):
    # --- Permission Check ---
    accounts = session.exec(select(Account).where(Account.id.in_(task_create.account_ids))).all()
    valid_accounts = PermissionService.filter_accounts_for_action(accounts, "invite")
    
    if not valid_accounts:
        raise HTTPException(status_code=400, detail="Selected accounts are not allowed to perform Invites (Tier Restriction)")
        
    valid_ids = [acc.id for acc in valid_accounts]

    # Convert lists to JSON strings for storage
    task_data = task_create.dict()
    task_data['account_ids_json'] = json.dumps(valid_ids) # Use validated IDs
    task_data['target_user_ids_json'] = json.dumps(task_create.target_user_ids)
    
    # Remove original list fields to match SQLModel
    del task_data['account_ids']
    del task_data['target_user_ids']
    
    db_task = InviteTask(**task_data)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # Trigger Celery Task
    celery_app.send_task("app.worker_invite.execute_invite_task", args=[db_task.id])
    
    return db_task

@router.get("/tasks", response_model=List[InviteTaskRead])
def get_invite_tasks(
    session: Session = Depends(get_session)
):
    from sqlmodel import select
    return session.exec(select(InviteTask).order_by(InviteTask.created_at.desc())).all()
