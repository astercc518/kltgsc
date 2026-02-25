from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Dict
import json
from app.core.db import get_session
from app.models.script import Script, ScriptCreate, ScriptRead, ScriptTask, ScriptTaskCreate, ScriptTaskRead
from app.services.script_service import ScriptService
from app.worker import execute_script_task

router = APIRouter()

# --- Scripts ---

@router.post("", response_model=ScriptRead)
def create_script(
    script: ScriptCreate,
    session: Session = Depends(get_session)
):
    """创建剧本"""
    db_script = Script.model_validate(script)
    session.add(db_script)
    session.commit()
    session.refresh(db_script)
    return db_script

@router.get("", response_model=List[ScriptRead])
def get_scripts(
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """获取剧本列表"""
    return session.exec(select(Script).offset(skip).limit(limit).order_by(Script.id.desc())).all()

# --- Script Tasks --- (放在 /{script_id} 路由之前避免路径冲突)

@router.post("/tasks", response_model=ScriptTaskRead)
def create_script_task(
    task: ScriptTaskCreate,
    session: Session = Depends(get_session)
):
    """创建并启动炒群任务"""
    # Verify script exists
    script = session.get(Script, task.script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
        
    if not script.lines_json:
        raise HTTPException(status_code=400, detail="Script content not generated yet")

    db_task = ScriptTask.model_validate(task)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # Start worker
    execute_script_task.delay(db_task.id)
    
    return db_task

@router.get("/tasks", response_model=List[ScriptTaskRead])
def get_script_tasks(
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """获取任务列表"""
    return session.exec(select(ScriptTask).offset(skip).limit(limit).order_by(ScriptTask.id.desc())).all()

# --- Single Script Routes ---

@router.get("/{script_id}", response_model=ScriptRead)
def get_script(
    script_id: int,
    session: Session = Depends(get_session)
):
    """获取单个剧本"""
    script = session.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script

@router.post("/{script_id}/generate")
async def generate_script_content(
    script_id: int,
    session: Session = Depends(get_session)
):
    """使用 LLM 生成剧本对话内容"""
    service = ScriptService(session)
    try:
        lines = await service.generate_script_lines(script_id)
        return {"status": "success", "lines": lines}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
