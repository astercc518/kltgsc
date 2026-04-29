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
    protocol: Optional[str] = None  # 强制指定协议，为空时自动检测
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


def _parse_proxy_line(proxy_str: str, force_protocol: Optional[str] = None) -> dict:
    """
    解析代理字符串，自动识别协议。

    支持格式：
      SOCKS5/HTTP:  host:port  |  host:port:user:pass
      MTProto:      host:port:secret  |  host:port:client_id:secret
        - client_id 为纯数字时自动识别为 MTProto 格式
        - secret 为 base64url 或 hex 长字符串 (≥20字符)

    示例 MTProto 行：
      45.86.246.136:443:6669869:7vwj9LI4n-y0UyIEqfmEwyF3aWxkYmVycmllcy5ydQ
    """
    import re

    parts = proxy_str.strip().split(':')
    if len(parts) < 2:
        raise ValueError("格式错误：至少需要 host:port")

    ip = parts[0]
    port = int(parts[1])

    # 如果调用方强制指定了协议，跳过自动检测
    if force_protocol:
        if force_protocol == "mtproto":
            # host:port:secret 或 host:port:client_id:secret
            if len(parts) == 3:
                return {"ip": ip, "port": port, "protocol": "mtproto",
                        "username": None, "password": parts[2]}
            elif len(parts) >= 4:
                return {"ip": ip, "port": port, "protocol": "mtproto",
                        "username": parts[2], "password": parts[3]}
            raise ValueError("MTProto 格式需要 secret 字段")
        else:
            username = parts[2] if len(parts) > 2 else None
            password = parts[3] if len(parts) > 3 else None
            return {"ip": ip, "port": port, "protocol": force_protocol,
                    "username": username, "password": password}

    # --- 自动检测 ---
    # 规则 1：4段，第3段为纯数字（client_id），第4段为长字符串 → MTProto
    if len(parts) == 4 and parts[2].isdigit():
        secret_candidate = parts[3]
        if len(secret_candidate) >= 20 and re.fullmatch(r'[A-Za-z0-9+/=_\-]+', secret_candidate):
            return {"ip": ip, "port": port, "protocol": "mtproto",
                    "username": parts[2], "password": secret_candidate}

    # 规则 2：3段，第3段为长 base64url/hex 字符串 → MTProto（无 client_id）
    if len(parts) == 3:
        secret_candidate = parts[2]
        is_base64url = len(secret_candidate) >= 20 and re.fullmatch(r'[A-Za-z0-9+/=_\-]+', secret_candidate)
        is_hex = len(secret_candidate) >= 32 and re.fullmatch(r'[0-9a-fA-F]+', secret_candidate) and len(secret_candidate) % 2 == 0
        if is_base64url or is_hex:
            return {"ip": ip, "port": port, "protocol": "mtproto",
                    "username": None, "password": secret_candidate}

    # 默认：SOCKS5
    username = parts[2] if len(parts) > 2 else None
    password = parts[3] if len(parts) > 3 else None
    return {"ip": ip, "port": port, "protocol": "socks5",
            "username": username, "password": password}


@router.post("/batch/upload")
def upload_proxies_batch(
    request: BatchUploadRequest,
    session: Session = Depends(get_session)
):
    """批量上传代理。

    支持 SOCKS5/HTTP 格式：  host:port  |  host:port:user:pass
    支持 MTProto 格式：       host:port:secret  |  host:port:client_id:secret
    可通过 protocol 字段强制指定协议（"socks5"/"http"/"mtproto"）。
    """
    created = 0
    errors = []

    proxy_list = request.proxies or []
    if request.proxies_text:
        proxy_list = [line.strip() for line in request.proxies_text.strip().split('\n') if line.strip()]

    for proxy_str in proxy_list:
        try:
            parsed = _parse_proxy_line(proxy_str, force_protocol=request.protocol)

            existing = session.exec(
                select(Proxy).where(
                    Proxy.ip == parsed["ip"],
                    Proxy.port == parsed["port"]
                )
            ).first()
            if existing:
                continue

            # MTProto 无法用 HTTP 验证，供应商数据可信，直接 active
            initial_status = "active" if parsed["protocol"] == "mtproto" else "unknown"
            proxy = Proxy(
                ip=parsed["ip"],
                port=parsed["port"],
                username=parsed["username"],
                password=parsed["password"],
                protocol=parsed["protocol"],
                category=request.category,
                provider_type=request.provider_type or ("datacenter" if parsed["protocol"] == "mtproto" else None),
                status=initial_status,
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

        # SOCKS5/HTTP 检测会返回 details，MTProto 不返回（无需处理）
        if details:
            if details.get('country'):
                proxy.country = details.get('country')

            hosting = details.get('hosting', False)
            isp = details.get('isp', '')
            if hosting:
                proxy.provider_type = "datacenter"
            elif isp:
                proxy.provider_type = "isp"

    else:
        if proxy.protocol == "mtproto":
            # MTProto 的 TCP 测试不可靠（服务端会因无握手包断连）
            # 失败不视为"死亡"，保留当前状态，只增加失败计数
            proxy.fail_count = (proxy.fail_count or 0) + 1
            if proxy.fail_count >= 5:
                # 连续失败 5 次再标 dead
                proxy.status = "dead"
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
