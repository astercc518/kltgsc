import json
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.script import Script, ScriptCreate, ScriptRead, ScriptTask, ScriptTaskCreate, ScriptTaskRead
from app.worker import execute_script_task

router = APIRouter()

# --- Script CRUD ---

@router.post("/", response_model=ScriptRead)
def create_script(
    script: ScriptCreate,
    session: Session = Depends(get_session)
):
    """创建新的剧本"""
    # roles list -> json string
    db_script = Script(
        name=script.name,
        topic=script.topic,
        background_story=script.background_story,
        roles_json=json.dumps(script.roles)
    )
    session.add(db_script)
    session.commit()
    session.refresh(db_script)
    
    # Return with parsed roles
    return ScriptRead(
        **db_script.dict(),
        roles=json.loads(db_script.roles_json)
    )

@router.get("/", response_model=List[ScriptRead])
def get_scripts(
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    scripts = session.exec(select(Script).offset(skip).limit(limit).order_by(Script.created_at.desc())).all()
    results = []
    for s in scripts:
        results.append(ScriptRead(
            **s.dict(),
            roles=json.loads(s.roles_json)
        ))
    return results

@router.get("/{script_id}", response_model=ScriptRead)
def get_script(
    script_id: int,
    session: Session = Depends(get_session)
):
    script = session.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptRead(
        **script.dict(),
        roles=json.loads(script.roles_json)
    )

@router.delete("/{script_id}")
def delete_script(
    script_id: int,
    session: Session = Depends(get_session)
):
    script = session.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    session.delete(script)
    session.commit()
    return {"status": "success", "message": "Script deleted"}

# --- Task CRUD ---

@router.post("/tasks", response_model=ScriptTaskRead)
def create_script_task(
    task: ScriptTaskCreate,
    session: Session = Depends(get_session)
):
    """创建并启动炒群任务"""
    # mapping -> json
    db_task = ScriptTask(
        script_id=task.script_id,
        group_link=task.group_link,
        max_turns=task.max_turns,
        min_delay=task.min_delay,
        max_delay=task.max_delay,
        account_mapping_json=json.dumps(task.account_mapping)
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # Start Worker
    execute_script_task.delay(db_task.id)
    
    return ScriptTaskRead(
        **db_task.dict(),
        account_mapping=json.loads(db_task.account_mapping_json)
    )

@router.get("/tasks", response_model=List[ScriptTaskRead])
def get_script_tasks(
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    tasks = session.exec(select(ScriptTask).offset(skip).limit(limit).order_by(ScriptTask.created_at.desc())).all()
    results = []
    for t in tasks:
        results.append(ScriptTaskRead(
            **t.dict(),
            account_mapping=json.loads(t.account_mapping_json)
        ))
    return results
