import json
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.warmup_task import WarmupTask, WarmupTaskCreate, WarmupTaskRead
from app.models.warmup_template import WarmupTemplate, WarmupTemplateCreate, WarmupTemplateRead, WarmupTemplateUpdate
from app.worker import execute_warmup_task

router = APIRouter()

# =====================
# Template CRUD
# =====================

@router.post("/templates", response_model=WarmupTemplateRead)
def create_template(
    template: WarmupTemplateCreate,
    session: Session = Depends(get_session)
):
    """创建养号模板"""
    db_template = WarmupTemplate(**template.dict())
    
    # 如果设置为默认模板，取消其他默认
    if db_template.is_default:
        existing_defaults = session.exec(select(WarmupTemplate).where(WarmupTemplate.is_default == True)).all()
        for t in existing_defaults:
            t.is_default = False
            session.add(t)
    
    session.add(db_template)
    session.commit()
    session.refresh(db_template)
    return db_template

@router.get("/templates", response_model=List[WarmupTemplateRead])
def get_templates(
    session: Session = Depends(get_session)
):
    """获取所有养号模板"""
    templates = session.exec(select(WarmupTemplate).order_by(WarmupTemplate.is_default.desc(), WarmupTemplate.created_at.desc())).all()
    return templates

@router.get("/templates/{template_id}", response_model=WarmupTemplateRead)
def get_template(
    template_id: int,
    session: Session = Depends(get_session)
):
    """获取单个模板"""
    template = session.get(WarmupTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/templates/{template_id}", response_model=WarmupTemplateRead)
def update_template(
    template_id: int,
    update: WarmupTemplateUpdate,
    session: Session = Depends(get_session)
):
    """更新养号模板"""
    template = session.get(WarmupTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = update.dict(exclude_unset=True)
    
    # 如果设置为默认模板，取消其他默认
    if update_data.get("is_default"):
        existing_defaults = session.exec(select(WarmupTemplate).where(WarmupTemplate.is_default == True, WarmupTemplate.id != template_id)).all()
        for t in existing_defaults:
            t.is_default = False
            session.add(t)
    
    for key, value in update_data.items():
        setattr(template, key, value)
    
    template.updated_at = datetime.utcnow()
    session.add(template)
    session.commit()
    session.refresh(template)
    return template

@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    session: Session = Depends(get_session)
):
    """删除养号模板"""
    template = session.get(WarmupTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    session.delete(template)
    session.commit()
    return {"message": "Template deleted", "id": template_id}

# =====================
# Task CRUD
# =====================

@router.post("/tasks", response_model=WarmupTaskRead)
async def create_warmup_task(
    task_create: WarmupTaskCreate,
    session: Session = Depends(get_session)
):
    """创建并启动养号任务"""
    # 1. 创建任务记录
    # 手动处理 account_ids -> json
    task_data = task_create.dict(exclude={"account_ids"})
    task = WarmupTask(**task_data)
    task.account_ids_json = json.dumps(task_create.account_ids)
    
    session.add(task)
    session.commit()
    session.refresh(task)
    
    # 2. 启动异步 Worker
    execute_warmup_task.delay(task.id)
    
    # 返回时需要构造 account_ids
    return WarmupTaskRead(
        **task.dict(),
        account_ids=task_create.account_ids
    )

@router.get("/tasks", response_model=List[WarmupTaskRead])
def get_warmup_tasks(
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """获取养号任务列表"""
    tasks = session.exec(select(WarmupTask).offset(skip).limit(limit).order_by(WarmupTask.created_at.desc())).all()
    
    # Convert to Read model
    results = []
    for t in tasks:
        results.append(WarmupTaskRead(
            **t.dict(),
            account_ids=json.loads(t.account_ids_json)
        ))
    return results
