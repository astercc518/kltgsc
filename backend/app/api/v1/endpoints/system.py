from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from app.core.db import get_session
from app.models.system_config import SystemConfig
from app.models.account import Account
from app.models.send_task import SendTask, SendRecord
from app.models.lead import Lead

router = APIRouter()

# --- System Config ---

@router.get("/config", response_model=List[SystemConfig])
def get_system_config(session: Session = Depends(get_session)):
    return session.exec(select(SystemConfig)).all()

@router.get("/config/{key}", response_model=SystemConfig)
def get_config_by_key(key: str, session: Session = Depends(get_session)):
    config = session.get(SystemConfig, key)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config

@router.post("/config", response_model=SystemConfig)
def set_system_config(
    key: str = Body(...),
    value: str = Body(...),
    description: str = Body(None),
    session: Session = Depends(get_session)
):
    config = session.get(SystemConfig, key)
    if config:
        config.value = value
        if description:
            config.description = description
        config.updated_at = datetime.utcnow()
    else:
        config = SystemConfig(key=key, value=value, description=description)
        session.add(config)
    
    session.commit()
    session.refresh(config)
    return config

# --- Statistics ---

@router.get("/stats/overview")
def get_overview_stats(session: Session = Depends(get_session)):
    """获取总体统计数据"""
    # 账号统计
    total_accounts = session.exec(select(func.count(Account.id))).one()
    active_accounts = session.exec(select(func.count(Account.id)).where(Account.status == "active")).one()
    banned_accounts = session.exec(select(func.count(Account.id)).where(Account.status == "banned")).one()
    
    # 消息统计 (今日)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sent = session.exec(select(func.count(SendRecord.id)).where(SendRecord.sent_at >= today)).one()
    
    # 线索统计
    total_leads = session.exec(select(func.count(Lead.id))).one()
    new_leads_today = session.exec(select(func.count(Lead.id)).where(Lead.created_at >= today)).one()
    
    return {
        "accounts": {
            "total": total_accounts,
            "active": active_accounts,
            "banned": banned_accounts,
            "survival_rate": round(active_accounts / total_accounts * 100, 1) if total_accounts > 0 else 0
        },
        "messages": {
            "today_sent": today_sent
        },
        "leads": {
            "total": total_leads,
            "new_today": new_leads_today
        }
    }

@router.get("/stats/daily_trend")
def get_daily_trend(days: int = 7, session: Session = Depends(get_session)):
    """获取每日发送趋势"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # SQLite doesn't have sophisticated date functions like Postgres, doing simple grouping in Python or basic SQL
    # For SendRecord
    records = session.exec(
        select(SendRecord.sent_at, SendRecord.status)
        .where(SendRecord.sent_at >= start_date)
    ).all()
    
    # Process in memory
    stats = {}
    for r in records:
        date_str = r.sent_at.strftime("%Y-%m-%d")
        if date_str not in stats:
            stats[date_str] = {"success": 0, "failed": 0, "total": 0}
        
        stats[date_str]["total"] += 1
        if r.status == "success":
            stats[date_str]["success"] += 1
        else:
            stats[date_str]["failed"] += 1
            
    # Fill missing days
    result = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        data = stats.get(d, {"success": 0, "failed": 0, "total": 0})
        result.append({"date": d, **data})
        
    return list(reversed(result))
