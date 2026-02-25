"""
营销群发 API
支持安全发送、发送计划预览、分批发送
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from app.core.db import get_session
from app.models.send_task import SendTask, SendTaskCreate, SendTaskRead, SendRecord
from app.models.account import Account
from app.models.account_stats import AccountSendStats
from app.tasks.marketing_tasks import execute_send_task
from app.services.permission_service import PermissionService
from app.services.safe_send_dispatcher import SafeSendDispatcher, SafeSendConfig

router = APIRouter()


class SendPlanRequest(BaseModel):
    """发送计划请求"""
    account_ids: List[int]
    target_user_ids: List[int]


class SendPlanResponse(BaseModel):
    """发送计划响应"""
    total_targets: int
    total_capacity_today: int
    can_complete_today: bool
    batches_needed: int
    sends_today: int
    sends_remaining: int
    estimated_hours_today: float
    estimated_days_total: int
    accounts_available: int
    avg_per_account: float
    accounts_summary: List[dict]


class SafeSendConfigUpdate(BaseModel):
    """安全发送配置更新"""
    max_daily_sends_new: Optional[int] = None
    max_daily_sends_normal: Optional[int] = None
    max_daily_sends_trusted: Optional[int] = None
    min_delay_seconds: Optional[int] = None
    max_delay_seconds: Optional[int] = None
    sends_before_rest: Optional[int] = None
    rest_duration_min: Optional[int] = None
    rest_duration_max: Optional[int] = None


@router.post("/plan", response_model=SendPlanResponse)
def get_send_plan(
    request: SendPlanRequest,
    session: Session = Depends(get_session)
):
    """
    预览发送计划
    
    返回：
    - 今日可发送数量
    - 需要分几批完成
    - 预计耗时
    - 各账号配额情况
    """
    # 权限检查
    accounts = session.exec(
        select(Account).where(Account.id.in_(request.account_ids))
    ).all()
    valid_accounts = PermissionService.filter_accounts_for_action(accounts, "mass_dm")
    
    if not valid_accounts:
        raise HTTPException(
            status_code=400, 
            detail="No accounts are allowed to perform Mass DM (Tier Restriction)"
        )
    
    valid_account_ids = [acc.id for acc in valid_accounts]
    
    # 创建调度器获取计划
    dispatcher = SafeSendDispatcher(session)
    plan = dispatcher.create_send_plan(valid_account_ids, request.target_user_ids)
    
    # 获取账号摘要
    accounts_summary = dispatcher.get_account_stats_summary(valid_account_ids)
    
    return SendPlanResponse(
        **plan,
        accounts_summary=accounts_summary
    )


@router.post("/tasks", response_model=SendTaskRead)
def create_send_task(
    task: SendTaskCreate,
    session: Session = Depends(get_session)
):
    """
    创建并启动安全发送任务
    
    安全策略自动启用：
    - 每账号每日限额（新账号15条，普通30条，老账号50条）
    - 随机发送间隔（60-180秒）
    - 连续发送5条后休息5-15分钟
    - 智能账号轮换
    """
    # 权限检查
    accounts = session.exec(
        select(Account).where(Account.id.in_(task.account_ids))
    ).all()
    valid_accounts = PermissionService.filter_accounts_for_action(accounts, "mass_dm")
    
    if not valid_accounts:
        raise HTTPException(
            status_code=400, 
            detail="No accounts are allowed to perform Mass DM (Tier Restriction)"
        )
    
    valid_account_ids = [acc.id for acc in valid_accounts]
    
    # 检查容量
    dispatcher = SafeSendDispatcher(session)
    plan = dispatcher.create_send_plan(valid_account_ids, task.target_user_ids)
    
    if plan['total_capacity_today'] == 0:
        raise HTTPException(
            status_code=400,
            detail="All accounts have reached their daily sending limits. Please try again tomorrow."
        )
    
    # 创建任务
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
    
    # 启动任务
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


@router.get("/tasks/{task_id}")
def get_send_task_detail(
    task_id: int,
    session: Session = Depends(get_session)
):
    """获取任务详情，包括发送记录"""
    task = session.get(SendTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 获取发送记录
    records = session.exec(
        select(SendRecord).where(SendRecord.task_id == task_id).order_by(SendRecord.sent_at.desc()).limit(100)
    ).all()
    
    return {
        "task": task,
        "records": records,
        "progress": {
            "total": task.total_count,
            "success": task.success_count,
            "failed": task.fail_count,
            "pending": task.total_count - task.success_count - task.fail_count,
            "progress_percent": round((task.success_count + task.fail_count) / task.total_count * 100, 1) if task.total_count > 0 else 0
        }
    }


@router.post("/tasks/{task_id}/pause")
def pause_send_task(
    task_id: int,
    session: Session = Depends(get_session)
):
    """暂停发送任务"""
    task = session.get(SendTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "running":
        raise HTTPException(status_code=400, detail=f"Task is {task.status}, cannot pause")
    
    task.status = "paused"
    session.add(task)
    session.commit()
    
    return {"status": "paused", "message": "Task paused. It will stop after current message."}


@router.post("/tasks/{task_id}/cancel")
def cancel_send_task(
    task_id: int,
    session: Session = Depends(get_session)
):
    """取消发送任务"""
    task = session.get(SendTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == "completed":
        raise HTTPException(status_code=400, detail="Task already completed")
    
    task.status = "cancelled"
    session.add(task)
    session.commit()
    
    return {"status": "cancelled", "message": "Task cancelled."}


@router.get("/accounts/stats")
def get_accounts_send_stats(
    account_ids: str = None,  # comma separated
    session: Session = Depends(get_session)
):
    """
    获取账号发送统计
    
    返回每个账号今日的：
    - 已发送数量
    - 剩余配额
    - 成功率
    - 是否可用
    """
    if account_ids:
        ids = [int(x.strip()) for x in account_ids.split(",")]
    else:
        # 获取所有活跃账号
        accounts = session.exec(
            select(Account).where(Account.status == "active")
        ).all()
        ids = [acc.id for acc in accounts]
    
    dispatcher = SafeSendDispatcher(session)
    summary = dispatcher.get_account_stats_summary(ids)
    
    # 计算汇总
    total_capacity = sum(acc["remaining"] for acc in summary)
    available_count = sum(1 for acc in summary if acc["is_available"])
    
    return {
        "accounts": summary,
        "summary": {
            "total_accounts": len(summary),
            "available_accounts": available_count,
            "total_capacity_remaining": total_capacity
        }
    }


@router.get("/config")
def get_safe_send_config(session: Session = Depends(get_session)):
    """获取当前安全发送配置"""
    from app.models.system_config import SystemConfig
    
    # 默认配置
    defaults = {
        "max_daily_sends_new": 15,
        "max_daily_sends_normal": 30,
        "max_daily_sends_trusted": 50,
        "min_delay_seconds": 60,
        "max_delay_seconds": 180,
        "sends_before_rest": 5,
        "rest_duration_min": 300,
        "rest_duration_max": 900,
        "max_flood_wait_daily": 2,
        "cooldown_after_flood": 3600
    }
    
    result = {}
    for key, default_value in defaults.items():
        config_key = f"safe_send_{key}"
        config = session.exec(
            select(SystemConfig).where(SystemConfig.key == config_key)
        ).first()
        if config:
            result[key] = int(config.value)
        else:
            result[key] = default_value
    
    return result


@router.post("/config")
def update_safe_send_config(
    updates: dict,
    session: Session = Depends(get_session)
):
    """更新安全发送配置"""
    from app.models.system_config import SystemConfig
    
    valid_keys = [
        "max_daily_sends_new",
        "max_daily_sends_normal", 
        "max_daily_sends_trusted",
        "min_delay_seconds",
        "max_delay_seconds",
        "sends_before_rest",
        "rest_duration_min",
        "rest_duration_max",
        "max_flood_wait_daily",
        "cooldown_after_flood"
    ]
    
    updated = []
    for key, value in updates.items():
        if key not in valid_keys:
            continue
            
        config_key = f"safe_send_{key}"
        config = session.exec(
            select(SystemConfig).where(SystemConfig.key == config_key)
        ).first()
        
        if config:
            config.value = str(value)
        else:
            config = SystemConfig(key=config_key, value=str(value))
        
        session.add(config)
        updated.append(key)
    
    session.commit()
    
    return {"success": True, "updated": updated}
