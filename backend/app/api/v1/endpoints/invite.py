"""
批量拉人 API 端点
功能：
1. 创建拉人任务（支持高级筛选）
2. 任务管理（暂停/恢复/取消）
3. 实时进度查询
4. 日志查询
5. 账号统计
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.invite_task import InviteTask, InviteTaskCreate, InviteTaskRead, InviteTaskUpdate
from app.models.invite_log import InviteLog, InviteLogRead, InviteStats, AccountInviteStats
from app.models.target_user import TargetUser
from app.models.account import Account
from app.core.celery_app import celery_app
from app.services.permission_service import PermissionService
from app.services.invite_service import InviteService
import json
from datetime import datetime

router = APIRouter()


# ==================== 任务管理 ====================

@router.post("/tasks", response_model=InviteTaskRead)
def create_invite_task(
    task_create: InviteTaskCreate,
    session: Session = Depends(get_session)
):
    """
    创建拉人任务
    
    支持两种目标指定方式：
    1. 直接指定 target_user_ids
    2. 使用高级筛选条件（filter_tags, filter_min_score 等）
    """
    invite_service = InviteService(session)
    
    # === 账号验证 ===
    account_ids = task_create.account_ids
    if account_ids:
        accounts = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
        valid_accounts = PermissionService.filter_accounts_for_action(accounts, "invite")
        
        if not valid_accounts:
            raise HTTPException(
                status_code=400, 
                detail="所选账号不允许执行拉人操作（角色限制）"
            )
        account_ids = [acc.id for acc in valid_accounts]
    elif task_create.account_group:
        # 使用账号组
        available = invite_service.get_available_accounts(
            account_group=task_create.account_group,
            daily_limit=task_create.max_invites_per_account
        )
        if not available:
            raise HTTPException(
                status_code=400,
                detail=f"账号组 '{task_create.account_group}' 中没有可用账号"
            )
        account_ids = [acc.id for acc in available]
    else:
        raise HTTPException(
            status_code=400,
            detail="必须指定 account_ids 或 account_group"
        )
    
    # === 目标用户筛选 ===
    target_user_ids = task_create.target_user_ids
    if not target_user_ids:
        # 使用高级筛选
        targets = invite_service.filter_target_users(
            filter_tags=task_create.filter_tags,
            filter_min_score=task_create.filter_min_score,
            filter_funnel_stages=task_create.filter_funnel_stages,
            filter_source_groups=task_create.filter_source_groups,
            exclude_invited=task_create.exclude_invited,
            exclude_failed_recently=task_create.exclude_failed_recently,
            failed_cooldown_hours=task_create.failed_cooldown_hours,
            max_targets=task_create.max_targets
        )
        if not targets:
            raise HTTPException(
                status_code=400,
                detail="根据筛选条件未找到符合要求的目标用户"
            )
        target_user_ids = [t.id for t in targets]
    
    # === 创建任务 ===
    db_task = InviteTask(
        name=task_create.name,
        target_channel=task_create.target_channel,
        source_group=task_create.source_group,
        account_ids_json=json.dumps(account_ids),
        target_user_ids_json=json.dumps(target_user_ids),
        account_group=task_create.account_group,
        total_count=len(target_user_ids),
        pending_count=len(target_user_ids),
        min_delay=task_create.min_delay,
        max_delay=task_create.max_delay,
        max_invites_per_account=task_create.max_invites_per_account,
        max_invites_per_task=task_create.max_invites_per_task,
        concurrent_accounts=task_create.concurrent_accounts,
        stop_on_flood=task_create.stop_on_flood,
        filter_tags=json.dumps(task_create.filter_tags) if task_create.filter_tags else None,
        filter_min_score=task_create.filter_min_score,
        filter_funnel_stages=json.dumps(task_create.filter_funnel_stages) if task_create.filter_funnel_stages else None,
        exclude_invited=task_create.exclude_invited,
        exclude_failed_recently=task_create.exclude_failed_recently,
        failed_cooldown_hours=task_create.failed_cooldown_hours,
        scheduled_at=task_create.scheduled_at,
        is_recurring=task_create.is_recurring,
        recurring_interval_hours=task_create.recurring_interval_hours,
        recurring_batch_size=task_create.recurring_batch_size
    )
    
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # === 触发执行 ===
    if task_create.scheduled_at and task_create.scheduled_at > datetime.utcnow():
        # 定时任务 - 使用 Celery ETA
        celery_app.send_task(
            "app.tasks.invite_tasks.execute_invite_task", 
            args=[db_task.id],
            eta=task_create.scheduled_at
        )
    else:
        # 立即执行
        celery_app.send_task(
            "app.tasks.invite_tasks.execute_invite_task", 
            args=[db_task.id]
        )
    
    return db_task


@router.get("/tasks", response_model=List[InviteTaskRead])
def get_invite_tasks(
    status: Optional[str] = Query(None, description="筛选状态"),
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """获取拉人任务列表"""
    query = select(InviteTask)
    
    if status:
        query = query.where(InviteTask.status == status)
    
    query = query.order_by(InviteTask.created_at.desc()).offset(skip).limit(limit)
    
    tasks = session.exec(query).all()
    
    # 计算进度百分比
    result = []
    for task in tasks:
        task_dict = InviteTaskRead.model_validate(task)
        if task.total_count > 0:
            task_dict.progress_percent = round(
                (task.success_count + task.fail_count) / task.total_count * 100, 1
            )
            # 估算剩余时间
            if task.status == "running" and task.started_at:
                elapsed = (datetime.utcnow() - task.started_at).total_seconds()
                completed = task.success_count + task.fail_count
                if completed > 0:
                    avg_time = elapsed / completed
                    remaining = task.pending_count * avg_time
                    task_dict.estimated_remaining_minutes = int(remaining / 60)
        result.append(task_dict)
    
    return result


@router.get("/tasks/{task_id}", response_model=InviteTaskRead)
def get_invite_task(
    task_id: int,
    session: Session = Depends(get_session)
):
    """获取单个任务详情"""
    task = session.get(InviteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    result = InviteTaskRead.model_validate(task)
    if task.total_count > 0:
        result.progress_percent = round(
            (task.success_count + task.fail_count) / task.total_count * 100, 1
        )
    
    return result


@router.patch("/tasks/{task_id}", response_model=InviteTaskRead)
def update_invite_task(
    task_id: int,
    update: InviteTaskUpdate,
    session: Session = Depends(get_session)
):
    """更新任务状态（暂停/恢复/取消）"""
    task = session.get(InviteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if update.status:
        if update.status == "cancelled":
            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
        elif update.status == "paused":
            task.status = "paused"
        elif update.status == "running" and task.status == "paused":
            task.status = "pending"
            # 重新触发执行
            celery_app.send_task(
                "app.tasks.invite_tasks.execute_invite_task", 
                args=[task.id]
            )
    
    if update.min_delay is not None:
        task.min_delay = update.min_delay
    if update.max_delay is not None:
        task.max_delay = update.max_delay
    
    session.add(task)
    session.commit()
    session.refresh(task)
    
    return task


@router.delete("/tasks/{task_id}")
def delete_invite_task(
    task_id: int,
    session: Session = Depends(get_session)
):
    """删除任务"""
    task = session.get(InviteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status == "running":
        raise HTTPException(status_code=400, detail="无法删除运行中的任务，请先暂停")
    
    # 删除相关日志
    session.exec(select(InviteLog).where(InviteLog.task_id == task_id)).all()
    for log in session.exec(select(InviteLog).where(InviteLog.task_id == task_id)).all():
        session.delete(log)
    
    session.delete(task)
    session.commit()
    
    return {"message": "任务已删除"}


# ==================== 统计与日志 ====================

@router.get("/tasks/{task_id}/stats", response_model=InviteStats)
def get_task_stats(
    task_id: int,
    session: Session = Depends(get_session)
):
    """获取任务统计"""
    task = session.get(InviteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    invite_service = InviteService(session)
    return invite_service.get_task_stats(task_id)


@router.get("/tasks/{task_id}/logs", response_model=List[InviteLogRead])
def get_task_logs(
    task_id: int,
    status: Optional[str] = Query(None, description="筛选状态 success/failed"),
    limit: int = Query(50, le=200),
    session: Session = Depends(get_session)
):
    """获取任务日志"""
    query = select(InviteLog).where(InviteLog.task_id == task_id)
    
    if status:
        query = query.where(InviteLog.status == status)
    
    query = query.order_by(InviteLog.created_at.desc()).limit(limit)
    
    return session.exec(query).all()


# ==================== 账号统计 ====================

@router.get("/accounts/stats", response_model=List[AccountInviteStats])
def get_accounts_invite_stats(
    account_ids: Optional[str] = Query(None, description="账号ID列表，逗号分隔"),
    session: Session = Depends(get_session)
):
    """获取账号邀请统计"""
    invite_service = InviteService(session)
    
    if account_ids:
        ids = [int(x.strip()) for x in account_ids.split(",")]
    else:
        # 获取所有活跃账号
        accounts = session.exec(
            select(Account).where(Account.status == "active")
        ).all()
        ids = [acc.id for acc in accounts]
    
    stats = []
    for account_id in ids:
        stats.append(invite_service.get_account_invite_stats(account_id))
    
    return stats


# ==================== 目标用户预览 ====================

@router.post("/preview-targets")
def preview_targets(
    filter_tags: Optional[List[str]] = None,
    filter_min_score: Optional[int] = None,
    filter_funnel_stages: Optional[List[str]] = None,
    filter_source_groups: Optional[List[str]] = None,
    exclude_invited: bool = True,
    exclude_failed_recently: bool = True,
    failed_cooldown_hours: int = 72,
    max_targets: int = 100,
    session: Session = Depends(get_session)
):
    """
    预览筛选结果（不创建任务）
    用于向导式创建时展示将被拉入的用户列表
    """
    invite_service = InviteService(session)
    
    targets = invite_service.filter_target_users(
        filter_tags=filter_tags,
        filter_min_score=filter_min_score,
        filter_funnel_stages=filter_funnel_stages,
        filter_source_groups=filter_source_groups,
        exclude_invited=exclude_invited,
        exclude_failed_recently=exclude_failed_recently,
        failed_cooldown_hours=failed_cooldown_hours,
        max_targets=max_targets
    )
    
    return {
        "count": len(targets),
        "targets": [
            {
                "id": t.id,
                "telegram_id": t.telegram_id,
                "username": t.username,
                "first_name": t.first_name,
                "source_group": t.source_group,
                "ai_score": t.ai_score,
                "funnel_stage": t.funnel_stage,
                "invite_status": t.invite_status
            }
            for t in targets[:20]  # 只返回前20个预览
        ]
    }
