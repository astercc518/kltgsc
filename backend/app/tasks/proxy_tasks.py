"""
代理相关任务
- 批量检测代理
- 定时平衡代理-账号分配
"""
import time
import asyncio
import logging
from typing import List
from datetime import datetime, timedelta

import redis
from celery.exceptions import SoftTimeLimitExceeded
from sqlmodel import Session, select, col
from app.core.db import engine
from app.core.config import settings
from app.core.celery_app import celery_app
from app.models.proxy import Proxy
from app.models.account import Account
from app.services.proxy_checker import check_proxy_connectivity
from app.services.proxy_assigner import (
    assign_proxy_to_account,
    reassign_accounts_from_proxy,
    rebalance_overloaded_proxies,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 快速 TCP Ping（每 30 秒，全量，异步并发）
# ─────────────────────────────────────────────────────────────────────────────

async def _async_fast_ping_all(concurrency: int = 200, timeout: float = 5.0):
    """异步并发 TCP ping 全部代理，返回存活统计"""
    sem = asyncio.Semaphore(concurrency)

    async def _ping_one(proxy_id: int, ip: str, port: int) -> tuple:
        async with sem:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port), timeout=timeout
                )
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                return proxy_id, True
            except Exception:
                return proxy_id, False

    with Session(engine) as session:
        rows = session.exec(select(Proxy.id, Proxy.ip, Proxy.port, Proxy.protocol, Proxy.fail_count, Proxy.status)).all()

    tasks = [_ping_one(r.id, r.ip, r.port) for r in rows]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    # proxy_id → (protocol, fail_count, old_status, alive)
    meta = {r.id: (r.protocol, r.fail_count or 0, r.status) for r in rows}
    alive_map: dict[int, bool] = {}
    for item in raw:
        if isinstance(item, tuple):
            proxy_id, alive = item
            alive_map[proxy_id] = alive

    changed = 0
    now = datetime.utcnow()
    with Session(engine) as session:
        for proxy_id, alive in alive_map.items():
            proxy = session.get(Proxy, proxy_id)
            if not proxy:
                continue
            protocol, fail_count, old_status = meta[proxy_id]
            if alive:
                proxy.fail_count = 0
                new_status = "active"
            else:
                new_fail = fail_count + 1
                proxy.fail_count = new_fail
                # MTProto 需要连续 3 次失败才标 dead，其他 1 次
                threshold = 3 if protocol == "mtproto" else 1
                new_status = "dead" if new_fail >= threshold else old_status
            proxy.status = new_status
            proxy.last_checked = now
            session.add(proxy)
            if old_status != new_status:
                changed += 1
        session.commit()

    total = len(alive_map)
    alive_count = sum(1 for v in alive_map.values() if v)
    logger.info(f"Fast proxy ping done: {alive_count}/{total} alive, {changed} status changes")
    return {"total": total, "alive": alive_count, "dead": total - alive_count, "changed": changed}


@celery_app.task(bind=True, soft_time_limit=90, time_limit=120, max_retries=0)
def check_all_proxies_fast(self):
    """每 30 秒：TCP ping 全量代理（异步并发，不调 ip-api，不限速）"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_async_fast_ping_all())
    except Exception as e:
        logger.error(f"Fast proxy ping failed: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
def check_proxies_batch_task(self, proxy_ids: List[int]):
    """批量检测代理连通性（含 geo），空列表表示全量"""
    if not proxy_ids:
        with Session(engine) as session:
            proxy_ids = list(session.exec(select(Proxy.id)).all())
    logger.info(f"Checking {len(proxy_ids)} proxies (deep check)")
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    try:
        with Session(engine) as session:
            for proxy_id in proxy_ids:
                proxy = session.get(Proxy, proxy_id)
                if not proxy:
                    results["errors"].append(f"Proxy {proxy_id} not found")
                    results["failed"] += 1
                    continue

                try:
                    # Rate limiting for ip-api.com
                    time.sleep(1.5)

                    is_alive, error_msg, details = check_proxy_connectivity(proxy, fetch_details=True)

                    proxy.last_checked = datetime.utcnow()

                    if is_alive:
                        proxy.status = "active"
                        proxy.fail_count = 0
                        results["success"] += 1

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
                            # MTProto TCP 测试不可靠，连续失败 5 次才标 dead
                            proxy.fail_count = (proxy.fail_count or 0) + 1
                            if proxy.fail_count >= 5:
                                proxy.status = "dead"
                                results["failed"] += 1
                            else:
                                results["success"] += 1  # 计入成功，不打死
                        else:
                            proxy.status = "dead"
                            proxy.fail_count = (proxy.fail_count or 0) + 1
                            results["failed"] += 1

                    session.add(proxy)
                    session.commit()

                except Exception as e:
                    logger.error(f"Error checking proxy {proxy_id}: {e}")
                    proxy.status = "dead"
                    proxy.fail_count = (proxy.fail_count or 0) + 1
                    session.add(proxy)
                    session.commit()
                    results["failed"] += 1
                    results["errors"].append(str(e))
    except SoftTimeLimitExceeded:
        logger.error(f"Proxy batch check timed out. Checked {results['success'] + results['failed']} of {len(proxy_ids)} proxies")
        results["errors"].append("Task timed out")
        return results
    
    logger.info(f"Proxy check completed: {results['success']} success, {results['failed']} failed")
    return results


@celery_app.task(bind=True, max_retries=0, soft_time_limit=280, time_limit=300)
def rebalance_proxy_accounts(self):
    """
    定时代理-账号平衡任务 (每5分钟)
    6个子步骤：
    1. 死亡代理清理
    2. 过期代理清理
    3. 无代理账号修复
    4. 无效绑定清理
    5. 超载再平衡
    6. 过期代理检测
    """
    redis_client = redis.from_url(settings.REDIS_URL)
    lock = redis_client.lock("rebalance_proxy_accounts_lock", timeout=300)

    if not lock.acquire(blocking=False):
        logger.info("Rebalance task already running, skipping")
        return {"skipped": True, "reason": "lock_held"}

    try:
        stats = {}

        with Session(engine) as session:
            # ① 死亡代理清理
            dead_proxies = session.exec(
                select(Proxy).where(Proxy.status == "dead")
            ).all()
            dead_with_accounts = [p for p in dead_proxies if p.accounts]
            dead_migrated = 0
            dead_orphaned = 0
            for proxy in dead_with_accounts:
                result = reassign_accounts_from_proxy(session, proxy)
                dead_migrated += result["migrated"]
                dead_orphaned += result["orphaned"]
            session.commit()
            stats["step1_dead_proxies"] = {
                "found": len(dead_with_accounts),
                "migrated": dead_migrated,
                "orphaned": dead_orphaned,
            }
            logger.info(f"Step 1 - Dead proxy cleanup: {stats['step1_dead_proxies']}")

            # ② 过期代理清理
            now = datetime.utcnow()
            expired_proxies = session.exec(
                select(Proxy).where(
                    Proxy.expire_time != None,
                    col(Proxy.expire_time) < now,
                    Proxy.status != "dead",
                )
            ).all()
            expired_migrated = 0
            expired_orphaned = 0
            for proxy in expired_proxies:
                proxy.status = "dead"
                session.add(proxy)
                session.flush()
                result = reassign_accounts_from_proxy(session, proxy)
                expired_migrated += result["migrated"]
                expired_orphaned += result["orphaned"]
            session.commit()
            stats["step2_expired_proxies"] = {
                "found": len(expired_proxies),
                "migrated": expired_migrated,
                "orphaned": expired_orphaned,
            }
            logger.info(f"Step 2 - Expired proxy cleanup: {stats['step2_expired_proxies']}")

            # ③ 无代理账号修复
            unassigned_accounts = session.exec(
                select(Account).where(
                    col(Account.status).in_(["active", "init", "uploaded"]),
                    Account.proxy_id == None,
                )
            ).all()
            assigned_count = 0
            for account in unassigned_accounts:
                proxy = assign_proxy_to_account(session, account)
                if proxy:
                    account.proxy_id = proxy.id
                    session.add(account)
                    assigned_count += 1
            session.commit()
            stats["step3_unassigned_accounts"] = {
                "found": len(unassigned_accounts),
                "assigned": assigned_count,
            }
            logger.info(f"Step 3 - Unassigned account fix: {stats['step3_unassigned_accounts']}")

            # ④ 无效绑定清理 (账号绑定了已删除或 dead 的代理)
            invalid_accounts = session.exec(
                select(Account).where(
                    Account.proxy_id != None,
                    col(Account.status).in_(["active", "init", "uploaded"]),
                )
            ).all()
            invalid_fixed = 0
            for account in invalid_accounts:
                proxy = session.get(Proxy, account.proxy_id)
                if proxy is None or proxy.status == "dead":
                    account.proxy_id = None
                    session.flush()
                    new_proxy = assign_proxy_to_account(session, account)
                    if new_proxy:
                        account.proxy_id = new_proxy.id
                    session.add(account)
                    invalid_fixed += 1
            session.commit()
            stats["step4_invalid_bindings"] = {
                "checked": len(invalid_accounts),
                "fixed": invalid_fixed,
            }
            logger.info(f"Step 4 - Invalid binding cleanup: {stats['step4_invalid_bindings']}")

            # ⑤ 超载再平衡
            rebalance_result = rebalance_overloaded_proxies(session)
            session.commit()
            stats["step5_rebalance"] = rebalance_result
            logger.info(f"Step 5 - Overload rebalance: {stats['step5_rebalance']}")

            # ⑥ 过期代理检测 (last_checked 超 24h 的 active 代理)
            stale_cutoff = now - timedelta(hours=24)
            stale_proxies = session.exec(
                select(Proxy.id).where(
                    Proxy.status == "active",
                    (Proxy.last_checked == None) | (col(Proxy.last_checked) < stale_cutoff),
                )
            ).all()
            batches_dispatched = 0
            for i in range(0, len(stale_proxies), 50):
                batch = list(stale_proxies[i:i + 50])
                check_proxies_batch_task.delay(batch)
                batches_dispatched += 1
            stats["step6_stale_check"] = {
                "stale_proxies": len(stale_proxies),
                "batches_dispatched": batches_dispatched,
            }
            logger.info(f"Step 6 - Stale proxy check dispatch: {stats['step6_stale_check']}")

        logger.info(f"Rebalance task completed: {stats}")
        return stats

    except SoftTimeLimitExceeded:
        logger.warning("Rebalance task hit soft time limit, partial results may apply")
        return {"error": "soft_time_limit_exceeded"}
    except Exception as e:
        logger.error(f"Rebalance task failed: {e}", exc_info=True)
        raise
    finally:
        try:
            lock.release()
        except redis.exceptions.LockNotOwnedError:
            pass
