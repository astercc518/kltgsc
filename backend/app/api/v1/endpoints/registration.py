import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlmodel import Session
from pydantic import BaseModel

from app.core.db import get_session
from app.services.proxy_fetcher import ProxyFetcherService
from app.services.auto_register import AutoRegisterService

router = APIRouter()
logger = logging.getLogger(__name__)

class RegisterRequest(BaseModel):
    count: int = 1
    country: int = 0  # 0=Russia, 6=Indonesia
    proxy_category: str = "rotating"
    
class ProxyRefreshResponse(BaseModel):
    added_count: int

async def run_registration_task(count: int, country: int, proxy_category: str, session: Session):
    """后台任务：批量注册"""
    service = AutoRegisterService(session)
    success_count = 0
    fail_count = 0
    
    logger.info(f"Starting batch registration task: {count} accounts")
    
    for i in range(count):
        logger.info(f"Registering account {i+1}/{count}...")
        result = await service.register_account(country=country, proxy_category=proxy_category)
        
        if result["status"] == "success":
            success_count += 1
            logger.info(f"Account registered successfully: {result['phone']}")
        else:
            fail_count += 1
            logger.error(f"Registration failed: {result['message']}")
            
    logger.info(f"Batch registration finished. Success: {success_count}, Failed: {fail_count}")

@router.post("/start", response_model=dict)
async def start_auto_registration(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    启动自动注册任务 (后台运行)
    """
    if request.count < 1 or request.count > 100:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 100")
        
    # 注意：Session 在后台任务中可能会有问题，最好在后台任务中新建 Session
    # 这里为了演示方便先直接传，实际生产建议使用 SessionFactory
    background_tasks.add_task(run_registration_task, request.count, request.country, request.proxy_category, session)
    
    return {"status": "started", "message": f"Registration task for {request.count} accounts started in background"}

@router.post("/proxies/refresh", response_model=ProxyRefreshResponse)
async def refresh_proxies(
    session: Session = Depends(get_session)
):
    """
    手动触发从 IP2World 提取代理
    """
    fetcher = ProxyFetcherService(session)
    count = await fetcher.fetch_from_ip2world()
    return ProxyRefreshResponse(added_count=count)
