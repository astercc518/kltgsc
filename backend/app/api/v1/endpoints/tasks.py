from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from celery.result import AsyncResult
from app.core.celery_app import celery_app

router = APIRouter()

@router.post("/batch", response_model=Dict[str, Any])
def get_tasks_batch(
    task_ids: List[str] = Body(..., embed=True)
):
    """
    Get status of multiple tasks in a single request.
    Useful for reducing API calls when polling many tasks.
    """
    results = {}
    for task_id in task_ids:
        task_result = AsyncResult(task_id, app=celery_app)
        response = {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result if task_result.ready() else None,
        }
        
        # Handle specific metadata if available (e.g. for progress updates)
        if task_result.status == 'PROGRESS' and isinstance(task_result.info, dict):
            response["progress"] = task_result.info
            
        # Handle exceptions serialization
        if task_result.failed():
            response["error"] = str(task_result.result)
            
        results[task_id] = response
        
    return {"tasks": results}

@router.get("/active", response_model=Dict[str, Any])
def get_active_tasks():
    """
    Get list of currently executing tasks from Celery workers
    """
    inspector = celery_app.control.inspect()
    if not inspector:
        return {"active": {}, "reserved": {}, "scheduled": {}}
        
    return {
        "active": inspector.active() or {},
        "reserved": inspector.reserved() or {},
        "scheduled": inspector.scheduled() or {}
    }

@router.get("/{task_id}", response_model=Dict[str, Any])
def get_task_status(task_id: str):
    """
    Get status of a specific task
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None,
    }
    
    # Handle specific metadata if available (e.g. for progress updates)
    if task_result.status == 'PROGRESS' and isinstance(task_result.info, dict):
         response["progress"] = task_result.info
         
    # Handle exceptions serialization
    if task_result.failed():
        response["error"] = str(task_result.result)
        
    return response

@router.delete("/{task_id}")
def revoke_task(
    task_id: str,
    terminate: bool = Query(False, description="Whether to terminate the task execution immediately")
):
    """
    Revoke (cancel) a task
    """
    celery_app.control.revoke(task_id, terminate=terminate)
    return {"status": "revoked", "task_id": task_id, "terminate": terminate}

@router.post("/{task_id}/revoke")
def revoke_task_post(
    task_id: str,
    terminate: bool = Query(False, description="Whether to terminate the task execution immediately")
):
    """
    Revoke (cancel) a task (POST version for frontend compatibility)
    """
    celery_app.control.revoke(task_id, terminate=terminate)
    return {"status": "revoked", "task_id": task_id, "terminate": terminate}
