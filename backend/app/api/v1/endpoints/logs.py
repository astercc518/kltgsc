from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.operation_log import OperationLog, OperationLogCreate, OperationLogRead

router = APIRouter()

@router.post("/", response_model=OperationLogRead)
def create_log(
    log: OperationLogCreate,
    session: Session = Depends(get_session)
):
    """记录操作日志"""
    db_log = OperationLog.model_validate(log)
    session.add(db_log)
    session.commit()
    session.refresh(db_log)
    return db_log

@router.get("/", response_model=List[OperationLogRead])
def get_logs(
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取日志列表"""
    query = select(OperationLog)
    if action:
        query = query.where(OperationLog.action == action)
    
    query = query.offset(skip).limit(limit).order_by(OperationLog.created_at.desc())
    return session.exec(query).all()
