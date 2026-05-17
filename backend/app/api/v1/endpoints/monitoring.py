"""
实时监控统计 API
- GET /monitoring/stats  返回账号/代理/养号的全量快照
- POST /monitoring/trigger-check  手动触发快速检测
"""
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func

from app.core.db import get_session
from app.models.account import Account
from app.models.proxy import Proxy
from app.models.warmup_task import WarmupTask

router = APIRouter()


@router.get("/stats")
def get_monitoring_stats(session: Session = Depends(get_session)):
    """实时快照：账号状态分布 + 代理健康 + 养号情况 + 角色分布"""
    # ── 账号 ──────────────────────────────────────────────────────
    accounts = session.exec(select(Account)).all()
    acct_status = Counter(a.status for a in accounts)
    role_cnt = Counter(a.combat_role for a in accounts)

    # 最近 1 小时内封号数
    cutoff = datetime.utcnow() - timedelta(hours=1)
    banned_1h = sum(
        1 for a in accounts
        if a.status in ("banned", "spam_block") and a.last_active and a.last_active > cutoff
    )

    # ── 代理 ──────────────────────────────────────────────────────
    proxies = session.exec(select(Proxy)).all()
    proxy_status = Counter(p.status for p in proxies)
    total_proxies = len(proxies)
    active_proxies = proxy_status.get("active", 0)
    active_rate = round(active_proxies / total_proxies * 100, 1) if total_proxies else 0.0

    # 代理国家分布（top 5）
    country_cnt = Counter(p.country for p in proxies if p.country and p.status == "active")
    top_countries = [{"country": c, "count": n} for c, n in country_cnt.most_common(5)]

    # ── 养号任务 ──────────────────────────────────────────────────
    running_warmups = session.exec(
        select(func.count(WarmupTask.id)).where(WarmupTask.status == "running")
    ).one()

    # ── 告警 ──────────────────────────────────────────────────────
    alerts = []
    if active_rate < 50:
        alerts.append({"level": "critical", "msg": f"代理存活率仅 {active_rate}%，已低于 50%"})
    elif active_rate < 80:
        alerts.append({"level": "warning", "msg": f"代理存活率 {active_rate}%，建议补充代理"})

    listener_count = role_cnt.get("scout", 0)
    if listener_count == 0:
        alerts.append({"level": "critical", "msg": "无 listener (scout) 账号，trigger_ai 无法运行"})

    actor_count = role_cnt.get("actor", 0)
    if actor_count < 3:
        alerts.append({"level": "warning", "msg": f"actor 账号仅 {actor_count} 个，炒群效果受限"})

    if banned_1h >= 5:
        alerts.append({"level": "warning", "msg": f"最近 1 小时内 {banned_1h} 个账号被封/限制"})

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "accounts": {
            "total": len(accounts),
            "active": acct_status.get("active", 0),
            "banned": acct_status.get("banned", 0),
            "spam_block": acct_status.get("spam_block", 0),
            "stale": acct_status.get("stale", 0),
            "error": acct_status.get("error", 0),
            "banned_1h": banned_1h,
        },
        "proxies": {
            "total": total_proxies,
            "active": active_proxies,
            "dead": proxy_status.get("dead", 0),
            "active_rate": active_rate,
            "top_countries": top_countries,
        },
        "roles": {
            "listener": listener_count,
            "actor": actor_count,
            "cannon": role_cnt.get("cannon", 0),
            "sniper": role_cnt.get("sniper", 0),
        },
        "warmup": {
            "running": running_warmups,
        },
        "alerts": alerts,
    }


@router.post("/trigger-check")
def trigger_manual_check():
    """手动触发一次快速代理 ping + 账号心跳"""
    from app.tasks.proxy_tasks import check_all_proxies_fast
    from app.tasks.account_tasks import batch_heartbeat_check

    proxy_task = check_all_proxies_fast.delay()
    account_task = batch_heartbeat_check.delay()

    return {
        "proxy_task_id": proxy_task.id,
        "account_task_id": account_task.id,
        "message": "检测任务已触发",
    }
