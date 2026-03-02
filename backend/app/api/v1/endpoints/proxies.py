import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Body, Form
from sqlmodel import Session, select, func, col, or_
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.db import get_session
from app.models.proxy import Proxy, ProxyCreate, ProxyRead
from app.models.account import Account
from app.services.proxy_fetcher import ProxyFetcherService
from app.services.proxy_assigner import assign_proxy_to_account
from app.worker import check_proxies_batch_task

router = APIRouter()


class IP2WorldSyncRequest(BaseModel):
    api_url: Optional[str] = None
    category: str = "static"


class BatchCheckRequest(BaseModel):
    proxy_ids: List[int]


class BatchDeleteRequest(BaseModel):
    proxy_ids: List[int]


class BatchUploadRequest(BaseModel):
    proxies: Optional[List[str]] = None
    proxies_text: Optional[str] = None
    category: str = "static"
    provider_type: Optional[str] = None
    expire_time: Optional[datetime] = None


class BatchSetExpireRequest(BaseModel):
    proxy_ids: List[int]
    expire_time: Optional[datetime] = None  # None = 清除过期时间


@router.get("/")
def get_proxies(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None
):
    """获取代理列表"""
    query = select(Proxy)
    if status:
        query = query.where(Proxy.status == status)
    if category:
        query = query.where(Proxy.category == category)
    query = query.offset(skip).limit(limit)
    proxies = session.exec(query).all()
    return proxies


@router.get("/count")
def get_proxy_count(
    session: Session = Depends(get_session),
    status: Optional[str] = None,
    category: Optional[str] = None
):
    """获取代理数量"""
    query = select(func.count(Proxy.id))
    if status:
        query = query.where(Proxy.status == status)
    if category:
        query = query.where(Proxy.category == category)
    count = session.exec(query).one()
    return {"total": count, "count": count, "status": status}


@router.post("/")
def create_proxy(
    proxy: ProxyCreate,
    session: Session = Depends(get_session)
):
    """创建代理"""
    db_proxy = Proxy.model_validate(proxy)
    session.add(db_proxy)
    session.commit()
    session.refresh(db_proxy)
    return db_proxy


@router.post("/batch/upload")
def upload_proxies_batch(
    request: BatchUploadRequest,
    session: Session = Depends(get_session)
):
    """批量上传代理"""
    created = 0
    errors = []
    
    # 支持两种格式：proxies 数组或 proxies_text 文本
    proxy_list = request.proxies or []
    if request.proxies_text:
        proxy_list = [line.strip() for line in request.proxies_text.strip().split('\n') if line.strip()]
    
    for proxy_str in proxy_list:
        try:
            # 解析代理字符串: host:port:username:password 或 host:port
            parts = proxy_str.strip().split(':')
            if len(parts) < 2:
                errors.append(f"Invalid format: {proxy_str}")
                continue
            
            ip = parts[0]
            port = int(parts[1])
            username = parts[2] if len(parts) > 2 else None
            password = parts[3] if len(parts) > 3 else None
            
            # 检查是否已存在
            existing = session.exec(
                select(Proxy).where(
                    Proxy.ip == ip,
                    Proxy.port == port
                )
            ).first()
            
            if existing:
                continue
            
            proxy = Proxy(
                ip=ip,
                port=port,
                username=username,
                password=password,
                protocol="socks5",
                category=request.category,
                provider_type=request.provider_type,
                status="unknown",
                expire_time=request.expire_time,
            )
            session.add(proxy)
            created += 1
            
        except Exception as e:
            errors.append(f"{proxy_str}: {str(e)}")
    
    session.commit()
    
    return {
        "message": f"Created {created} proxies",
        "created": created,
        "errors": errors[:10]
    }


@router.post("/batch/check")
async def check_proxies_batch(
    request: BatchCheckRequest,
    session: Session = Depends(get_session)
):
    """批量检测代理"""
    task = check_proxies_batch_task.delay(request.proxy_ids)
    return {
        "message": f"Started checking {len(request.proxy_ids)} proxies",
        "task_id": task.id
    }


@router.post("/batch/delete")
def delete_proxies_batch(
    request: BatchDeleteRequest,
    session: Session = Depends(get_session)
):
    """批量删除代理"""
    deleted = 0
    for proxy_id in request.proxy_ids:
        proxy = session.get(Proxy, proxy_id)
        if proxy:
            # 解绑关联账号，避免 FK 约束错误
            for account in list(proxy.accounts):
                account.proxy_id = None
                session.add(account)
            session.delete(proxy)
            deleted += 1

    session.commit()
    return {"message": f"Deleted {deleted} proxies", "deleted": deleted}


@router.post("/batch/delete-abnormal")
def delete_abnormal_proxies(session: Session = Depends(get_session)):
    """一键删除异常代理（dead）"""
    proxies = session.exec(
        select(Proxy).where(col(Proxy.status) == "dead")
    ).all()
    deleted_count = 0
    for proxy in proxies:
        # 解绑关联账号，避免 FK 约束错误
        for account in list(proxy.accounts):
            account.proxy_id = None
            session.add(account)
        session.delete(proxy)
        deleted_count += 1
    session.commit()
    return {"message": f"已删除 {deleted_count} 个异常代理", "deleted_count": deleted_count}


@router.post("/sync/ip2world")
async def sync_ip2world(
    request: IP2WorldSyncRequest,
    session: Session = Depends(get_session)
):
    """从 IP2World 同步代理"""
    fetcher = ProxyFetcherService(session)
    added_count = await fetcher.fetch_from_ip2world(request.api_url, request.category)
    
    return {
        "message": "Sync completed",
        "added": added_count
    }


@router.post("/refresh/ip2world")
async def refresh_ip2world(
    session: Session = Depends(get_session)
):
    """刷新 IP2World 代理"""
    fetcher = ProxyFetcherService(session)
    added_count = await fetcher.fetch_from_ip2world(category="static")
    
    return {
        "message": "Refresh completed",
        "added_count": added_count
    }


@router.get("/expired-count")
def get_expired_proxy_count(session: Session = Depends(get_session)):
    """获取过期/即将过期代理统计"""
    now = datetime.utcnow()
    soon = now + timedelta(days=3)

    expired_count = session.exec(
        select(func.count(Proxy.id)).where(
            Proxy.expire_time != None,
            col(Proxy.expire_time) < now,
            Proxy.status != "dead",
        )
    ).one()

    expiring_soon_count = session.exec(
        select(func.count(Proxy.id)).where(
            Proxy.expire_time != None,
            col(Proxy.expire_time) >= now,
            col(Proxy.expire_time) <= soon,
            Proxy.status != "dead",
        )
    ).one()

    return {
        "expired_count": expired_count,
        "expiring_soon_count": expiring_soon_count,
    }


@router.post("/batch/set-expire")
def batch_set_expire(
    request: BatchSetExpireRequest,
    session: Session = Depends(get_session),
):
    """批量设置代理过期时间"""
    updated = 0
    for proxy_id in request.proxy_ids:
        proxy = session.get(Proxy, proxy_id)
        if proxy:
            proxy.expire_time = request.expire_time
            session.add(proxy)
            updated += 1
    session.commit()
    return {"updated": updated}


@router.post("/batch/cleanup-expired")
def cleanup_expired_proxies(session: Session = Depends(get_session)):
    """清理过期代理：标记 dead，解绑账号并尝试迁移"""
    now = datetime.utcnow()

    # 1. 查询已过期且未标记 dead 的代理
    expired_proxies = session.exec(
        select(Proxy).where(
            Proxy.expire_time != None,
            col(Proxy.expire_time) < now,
            Proxy.status != "dead",
        )
    ).all()

    if not expired_proxies:
        return {"expired_count": 0, "migrated_count": 0, "unbound_count": 0}

    expired_ids = [p.id for p in expired_proxies]

    # 2. 收集受影响的账号
    affected_accounts = session.exec(
        select(Account).where(col(Account.proxy_id).in_(expired_ids))
    ).all()

    # 3. 标记过期代理为 dead
    for proxy in expired_proxies:
        proxy.status = "dead"
        session.add(proxy)

    # 4. 解绑所有受影响账号
    for account in affected_accounts:
        account.proxy_id = None
        session.add(account)

    session.commit()

    # 5. 尝试为受影响账号迁移到新代理
    migrated_count = 0
    for account in affected_accounts:
        session.refresh(account)
        new_proxy = assign_proxy_to_account(session, account)
        if new_proxy:
            account.proxy_id = new_proxy.id
            session.add(account)
            migrated_count += 1

    session.commit()

    unbound_count = len(affected_accounts) - migrated_count

    return {
        "expired_count": len(expired_proxies),
        "migrated_count": migrated_count,
        "unbound_count": unbound_count,
    }


# 动态路由放在最后，避免匹配 /batch/xxx 等静态路由
@router.delete("/{proxy_id}")
def delete_proxy(
    proxy_id: int,
    session: Session = Depends(get_session)
):
    """删除代理"""
    proxy = session.get(Proxy, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    # 解绑关联账号，避免 FK 约束错误
    for account in list(proxy.accounts):
        account.proxy_id = None
        session.add(account)
    session.delete(proxy)
    session.commit()
    return {"message": "Proxy deleted"}


@router.post("/{proxy_id}/check")
async def check_proxy(
    proxy_id: int,
    session: Session = Depends(get_session)
):
    """检测单个代理连通性"""
    from app.services.proxy_checker import check_proxy_connectivity_async
    
    proxy = session.get(Proxy, proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    # 检测代理 (获取详情)
    is_alive, error_msg, details = await check_proxy_connectivity_async(proxy, fetch_details=True)
    
    # 更新状态
    proxy.last_checked = datetime.utcnow()
    if is_alive:
        proxy.status = "active"
        proxy.fail_count = 0
        
        # 更新 IP 信息
        if details:
            if details.get('country'):
                proxy.country = details.get('country')
            
            # 自动识别类型
            hosting = details.get('hosting', False)
            isp = details.get('isp', '')
            
            if hosting:
                proxy.provider_type = "datacenter"
            elif isp:
                proxy.provider_type = "isp"
                
    else:
        proxy.status = "dead"
        proxy.fail_count = (proxy.fail_count or 0) + 1
    
    session.add(proxy)
    session.commit()
    session.refresh(proxy)
    
    return {
        "proxy_id": proxy_id,
        "status": proxy.status,
        "is_alive": is_alive,
        "error": error_msg,
        "last_checked": proxy.last_checked,
        "details": details
    }
