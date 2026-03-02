"""
代理分配服务
为账号自动分配可用的代理
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select, or_
from app.models.proxy import Proxy
from app.models.account import Account

logger = logging.getLogger(__name__)

# 每个代理最大绑定的账号数量建议值
# 建议保持在 1-3 之间以降低风控风险
MAX_ACCOUNTS_PER_PROXY = 3

def assign_proxy_to_account(session: Session, account: Account) -> Optional[Proxy]:
    """
    为账号分配一个可用的代理
    策略：
    1. 根据账号角色（Master/Worker）选择合适的代理类型
       - Master: 优先 ISP Static，其次 Datacenter Static。负载限制极低 (1)。
       - Worker: 优先 Rotating/Datacenter。负载限制较高 (5)。
    2. 过滤掉绑定账号数量已达到上限的代理
    3. 在剩余可用代理中，选择绑定数量最少的（负载均衡）
    """
    
    candidates = []
    max_accounts = MAX_ACCOUNTS_PER_PROXY

    # 过期时间过滤：排除24小时内即将过期的代理
    expire_cutoff = datetime.utcnow() + timedelta(hours=24)
    expire_filter = or_(Proxy.expire_time == None, Proxy.expire_time > expire_cutoff)

    # === 策略 1: 主账号 (Master) ===
    if account.role == "master":
        # 优先：Active + Static + ISP
        candidates = session.exec(
            select(Proxy).where(
                Proxy.status == "active",
                Proxy.category == "static",
                Proxy.provider_type == "isp",
                expire_filter,
            )
        ).all()

        # 降级策略：如果没有 ISP，找 Static DataCenter
        if not candidates:
            candidates = session.exec(
                select(Proxy).where(
                    Proxy.status == "active",
                    Proxy.category == "static",
                    expire_filter,
                )
            ).all()

        # 主账号的负载限制更严格
        max_accounts = 1

    # === 策略 2: 临时/群发账号 (Worker) ===
    else:
        # 优先：Active + Rotating (如果是用于群发) 或者任何 Active
        candidates = session.exec(
            select(Proxy).where(Proxy.status == "active", expire_filter)
        ).all()
        
        # 临时账号允许更高的共享率
        max_accounts = 5

    # 如果没有找到任何候选代理
    if not candidates:
        return None
    
    # 筛选未满员的代理
    valid_proxies = []
    proxy_counts = {}
    
    for proxy in candidates:
        # 获取该代理当前绑定的账号数
        count = len(proxy.accounts) if proxy.accounts else 0
        
        if count < max_accounts:
            valid_proxies.append(proxy)
            proxy_counts[proxy.id] = count
            
    if not valid_proxies:
        return None
    
    # 在可用代理中选择绑定数量最少的
    best_proxy_id = min(proxy_counts.items(), key=lambda x: x[1])[0]
    best_proxy = session.get(Proxy, best_proxy_id)
    
    return best_proxy

def auto_assign_proxy(session: Session, account: Account) -> bool:
    """
    自动为账号分配代理并更新账号信息
    返回: 是否成功分配
    """
    if account.proxy_id:
        # 检查现有代理是否仍然有效
        current_proxy = session.get(Proxy, account.proxy_id)
        if current_proxy and current_proxy.status == "active":
            return True
        else:
            # 代理不存在或不活跃，重新分配
            account.proxy_id = None
    
    proxy = assign_proxy_to_account(session, account)
    if proxy:
        account.proxy_id = proxy.id
        session.add(account)
        session.commit()
        return True

    return False


def reassign_accounts_from_proxy(session: Session, proxy: Proxy) -> dict:
    """
    将代理上的所有账号解绑并尝试重新分配到其他代理
    返回: {"migrated": int, "orphaned": int}
    """
    migrated = 0
    orphaned = 0

    accounts = list(proxy.accounts)
    if not accounts:
        return {"migrated": 0, "orphaned": 0}

    # 先解绑所有账号
    for account in accounts:
        account.proxy_id = None
        session.add(account)
    session.flush()

    # 尝试为每个账号重新分配代理
    for account in accounts:
        new_proxy = assign_proxy_to_account(session, account)
        if new_proxy:
            account.proxy_id = new_proxy.id
            session.add(account)
            migrated += 1
        else:
            orphaned += 1

    session.flush()
    return {"migrated": migrated, "orphaned": orphaned}


def rebalance_overloaded_proxies(session: Session) -> dict:
    """
    检查所有 active 代理是否超载，将多余账号迁移到其他代理
    超载判定：有 master 账号的代理 max=1，纯 worker 代理 max=5
    返回: {"checked": int, "moved": int, "skipped": int}
    """
    checked = 0
    moved = 0
    skipped = 0

    proxies = session.exec(
        select(Proxy).where(Proxy.status == "active")
    ).all()

    for proxy in proxies:
        accounts = list(proxy.accounts) if proxy.accounts else []
        if not accounts:
            continue
        checked += 1

        has_master = any(a.role == "master" for a in accounts)
        max_allowed = 1 if has_master else 5

        if len(accounts) <= max_allowed:
            continue

        # 按 health_score 升序排列，优先迁移低分账号
        sorted_accounts = sorted(accounts, key=lambda a: a.health_score)
        excess = sorted_accounts[:len(accounts) - max_allowed]

        for account in excess:
            # 先临时解绑
            account.proxy_id = None
            session.flush()

            new_proxy = assign_proxy_to_account(session, account)
            if new_proxy:
                account.proxy_id = new_proxy.id
                session.add(account)
                moved += 1
            else:
                # 找不到新代理，保留在当前代理（有代理好过没代理）
                account.proxy_id = proxy.id
                session.add(account)
                skipped += 1
            session.flush()

    return {"checked": checked, "moved": moved, "skipped": skipped}
