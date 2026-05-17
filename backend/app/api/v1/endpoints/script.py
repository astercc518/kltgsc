from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Dict, Optional
from pydantic import BaseModel
import json
from app.core.db import get_session
from app.models.script import Script, ScriptCreate, ScriptRead, ScriptTask, ScriptTaskCreate, ScriptTaskRead
from app.services.script_service import ScriptService
from app.services.ai_engine import AIEngine
from app.worker import execute_script_task

router = APIRouter()


class GenerateFromPersonasRequest(BaseModel):
    name: str
    description: Optional[str] = None
    topic: str
    persona_ids: List[int]
    duration_minutes: int = 5
    campaign_id: Optional[int] = None

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
    campaign_id: int = Query(default=None, description="关联战役ID，用于注入知识库内容"),
    session: Session = Depends(get_session)
):
    """使用 LLM 生成剧本对话内容（可选注入战役知识库）"""
    service = ScriptService(session)
    try:
        lines = await service.generate_script_lines(script_id, campaign_id=campaign_id)
        return {"status": "success", "lines": lines}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate-from-personas", response_model=ScriptRead)
async def generate_script_from_personas(
    request: GenerateFromPersonasRequest,
    session: Session = Depends(get_session),
):
    """
    从 AI 人设库一键生成炒群剧本。

    流程：
    1. 拉取选中的 personas
    2. 调用 ai_engine 生成 lines + roles
    3. 自动入库 Script 表
    """
    if not request.persona_ids:
        raise HTTPException(status_code=400, detail="persona_ids cannot be empty")
    if len(request.persona_ids) > 5:
        raise HTTPException(status_code=400, detail="最多支持 5 个角色")

    # 战役知识库注入（可选）
    knowledge = None
    if request.campaign_id:
        knowledge = AIEngine.get_campaign_knowledge(session, request.campaign_id)

    engine = AIEngine(session)
    try:
        result = await engine.generate_script_from_personas(
            topic=request.topic,
            persona_ids=request.persona_ids,
            duration_minutes=request.duration_minutes,
            knowledge=knowledge,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"剧本生成失败: {e}")

    # 入库 Script
    script = Script(
        name=request.name,
        description=request.description,
        topic=request.topic,
        roles_json=result["roles_json"],
        lines_json=result["lines_json"],
    )
    session.add(script)
    session.commit()
    session.refresh(script)
    return script
