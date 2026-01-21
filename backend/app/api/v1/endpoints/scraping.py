from typing import List, Optional
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select, func, SQLModel
from app.core.db import get_session
from app.models.account import Account
from app.models.target_user import TargetUser, TargetUserCreate, TargetUserRead
from app.models.scraping_task import ScrapingTask, ScrapingTaskRead
from app.services.telegram_client import join_group_with_client, scrape_group_members
from app.core.exceptions import AccountException
from app.core.celery_app import celery_app

router = APIRouter()

class JoinGroupRequest(SQLModel):
    account_id: int
    group_link: str

class JoinGroupsBatchRequest(SQLModel):
    account_ids: List[int]
    group_links: List[str]  # 多个群组链接

@router.post("/join", response_model=dict)
async def join_group(
    request: JoinGroupRequest,
    session: Session = Depends(get_session)
):
    """使用指定账号加入群组"""
    account = session.get(Account, request.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    try:
        success, msg = await join_group_with_client(account, request.group_link, db_session=session)
        if not success:
            raise HTTPException(status_code=400, detail=msg)
    except AccountException as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"status": "success", "message": msg}

@router.post("/join/batch", response_model=dict)
async def join_groups_batch(
    request: JoinGroupsBatchRequest,
    session: Session = Depends(get_session)
):
    """批量加入群组 - 使用多个账号加入多个群组"""
    # 验证账号存在
    valid_account_ids = []
    for aid in request.account_ids:
        account = session.get(Account, aid)
        if account and account.status == 'active':
            valid_account_ids.append(aid)
    
    if not valid_account_ids:
        raise HTTPException(status_code=400, detail="No valid active accounts found")
    
    # 过滤有效的群组链接
    valid_links = [link.strip() for link in request.group_links if link.strip()]
    if not valid_links:
        raise HTTPException(status_code=400, detail="No valid group links provided")
    
    # 创建任务记录
    scraping_task = ScrapingTask(
        task_type="join_batch",
        status="running",
        account_ids_json=json.dumps(valid_account_ids),
        group_links_json=json.dumps(valid_links)
    )
    session.add(scraping_task)
    session.commit()
    session.refresh(scraping_task)
    
    # 创建异步任务
    celery_task = celery_app.send_task(
        "app.worker.join_groups_batch_task",
        args=[valid_account_ids, valid_links, scraping_task.id]
    )
    
    # 更新任务记录的 celery_task_id
    scraping_task.celery_task_id = celery_task.id
    session.add(scraping_task)
    session.commit()
    
    return {
        "status": "started",
        "task_id": celery_task.id,
        "scraping_task_id": scraping_task.id,
        "account_count": len(valid_account_ids),
        "group_count": len(valid_links),
        "message": f"批量加群任务已启动：{len(valid_account_ids)} 个账号加入 {len(valid_links)} 个群组"
    }

class ScrapeRequest(SQLModel):
    account_id: int
    group_link: str
    limit: int = 100
    # 过滤选项
    filter_active_only: bool = False
    filter_has_photo: bool = False
    filter_has_username: bool = False

class ScrapeBatchRequest(SQLModel):
    account_ids: List[int]
    group_links: List[str]
    limit: int = 100
    # 过滤选项
    filter_active_only: bool = False
    filter_has_photo: bool = False
    filter_has_username: bool = False

@router.post("/scrape", response_model=dict)
async def scrape_members(
    request: ScrapeRequest,
    session: Session = Depends(get_session)
):
    """采集群成员 (支持高质量用户过滤)"""
    account = session.get(Account, request.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # 构造过滤配置
    filter_config = {
        "active_only": request.filter_active_only,
        "has_photo": request.filter_has_photo,
        "has_username": request.filter_has_username
    }
    # 如果所有过滤都是 False，则不传递 filter_config
    if not any(filter_config.values()):
        filter_config = None
        
    try:
        success, members = await scrape_group_members(
            account, 
            request.group_link, 
            request.limit, 
            db_session=session,
            filter_config=filter_config
        )
        if not success:
            # If scrape returns False (e.g. error in client creation), members might be empty or error string
            raise HTTPException(status_code=400, detail="Scraping failed")
            
        # Save members to DB
        saved_count = 0
        for m in members:
            # Check if exists
            exists = session.exec(select(TargetUser).where(TargetUser.telegram_id == m["telegram_id"])).first()
            if not exists:
                user = TargetUser(**m)
                session.add(user)
                saved_count += 1
        
        session.commit()
        return {"status": "success", "scraped_count": len(members), "new_saved": saved_count}
        
    except AccountException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/scrape/batch", response_model=dict)
async def scrape_members_batch(
    request: ScrapeBatchRequest,
    session: Session = Depends(get_session)
):
    """批量采集群成员 - 后台任务 (支持高质量用户过滤)
    
    过滤选项:
    - filter_active_only: 仅保留最近一周活跃用户
    - filter_has_photo: 仅保留有头像的用户
    - filter_has_username: 仅保留有用户名的用户
    """
    # 验证账号
    valid_account_ids = []
    for aid in request.account_ids:
        account = session.get(Account, aid)
        if account and account.status == 'active':
            valid_account_ids.append(aid)
    
    if not valid_account_ids:
        raise HTTPException(status_code=400, detail="No valid active accounts found")
    
    # 验证链接
    valid_links = [link.strip() for link in request.group_links if link.strip()]
    if not valid_links:
        raise HTTPException(status_code=400, detail="No valid group links provided")
    
    # 构造过滤配置
    filter_config = {
        "active_only": request.filter_active_only,
        "has_photo": request.filter_has_photo,
        "has_username": request.filter_has_username
    }
    # 如果所有过滤都是 False，则传递 None
    if not any(filter_config.values()):
        filter_config = None
    
    # 创建任务记录
    scraping_task = ScrapingTask(
        task_type="scrape_members_batch",
        status="running",
        account_ids_json=json.dumps(valid_account_ids),
        group_links_json=json.dumps(valid_links)
    )
    session.add(scraping_task)
    session.commit()
    session.refresh(scraping_task)
    
    # 发送 Celery 任务
    celery_task = celery_app.send_task(
        "app.worker.scrape_members_batch_task",
        args=[valid_account_ids, valid_links, request.limit, scraping_task.id, filter_config]
    )
    
    # 更新任务记录的 celery_task_id
    scraping_task.celery_task_id = celery_task.id
    session.add(scraping_task)
    session.commit()
    
    filter_desc = []
    if request.filter_active_only:
        filter_desc.append("仅活跃用户")
    if request.filter_has_photo:
        filter_desc.append("有头像")
    if request.filter_has_username:
        filter_desc.append("有用户名")
    filter_str = "，".join(filter_desc) if filter_desc else "无"
    
    return {
        "status": "started",
        "task_id": celery_task.id,
        "scraping_task_id": scraping_task.id,
        "account_count": len(valid_account_ids),
        "group_count": len(valid_links),
        "limit_per_group": request.limit,
        "filters": filter_str,
        "message": f"批量采集任务已启动：{len(valid_account_ids)} 个账号采集 {len(valid_links)} 个群组 (过滤: {filter_str})"
    }

@router.get("/users/count", response_model=dict)
def get_target_users_count(
    source_group: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取目标用户总数"""
    query = select(func.count(TargetUser.id))
    if source_group:
        query = query.where(TargetUser.source_group == source_group)
    
    count = session.exec(query).one()
    return {"total": count}

@router.get("/users", response_model=List[TargetUserRead])
def get_target_users(
    skip: int = 0,
    limit: int = 50,
    source_group: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取采集的目标用户列表"""
    query = select(TargetUser)
    if source_group:
        query = query.where(TargetUser.source_group == source_group)
    
    query = query.offset(skip).limit(limit).order_by(TargetUser.id.desc())
    return session.exec(query).all()

# =====================
# Task History
# =====================

@router.get("/tasks", response_model=List[ScrapingTaskRead])
def get_scraping_tasks(
    skip: int = 0,
    limit: int = 20,
    task_type: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取采集任务历史"""
    query = select(ScrapingTask)
    if task_type:
        query = query.where(ScrapingTask.task_type == task_type)
    
    query = query.offset(skip).limit(limit).order_by(ScrapingTask.created_at.desc())
    return session.exec(query).all()

@router.get("/tasks/{task_id}", response_model=dict)
def get_scraping_task_detail(
    task_id: int,
    session: Session = Depends(get_session)
):
    """获取采集任务详情"""
    task = session.get(ScrapingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "account_ids": json.loads(task.account_ids_json),
        "group_links": json.loads(task.group_links_json),
        "result": json.loads(task.result_json),
        "success_count": task.success_count,
        "fail_count": task.fail_count,
        "error_message": task.error_message,
        "celery_task_id": task.celery_task_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }
