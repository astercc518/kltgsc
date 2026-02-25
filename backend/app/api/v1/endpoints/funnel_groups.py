"""
营销群/私塘管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.funnel_group import FunnelGroup, FunnelGroupCreate, FunnelGroupUpdate, FunnelGroupRead

router = APIRouter()


@router.get("/", response_model=List[FunnelGroupRead])
def get_funnel_groups(
    skip: int = 0,
    limit: int = 50,
    type: Optional[str] = None,
    campaign_id: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """获取营销群列表"""
    query = select(FunnelGroup)
    if type:
        query = query.where(FunnelGroup.type == type)
    if campaign_id:
        query = query.where(FunnelGroup.campaign_id == campaign_id)
    query = query.offset(skip).limit(limit).order_by(FunnelGroup.created_at.desc())
    return session.exec(query).all()


@router.post("/", response_model=FunnelGroupRead)
def create_funnel_group(
    funnel_group: FunnelGroupCreate,
    session: Session = Depends(get_session)
):
    """创建营销群"""
    db_group = FunnelGroup(**funnel_group.dict())
    session.add(db_group)
    session.commit()
    session.refresh(db_group)
    return db_group


@router.get("/{group_id}", response_model=FunnelGroupRead)
def get_funnel_group(
    group_id: int,
    session: Session = Depends(get_session)
):
    """获取营销群详情"""
    group = session.get(FunnelGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Funnel group not found")
    return group


@router.put("/{group_id}", response_model=FunnelGroupRead)
def update_funnel_group(
    group_id: int,
    updates: FunnelGroupUpdate,
    session: Session = Depends(get_session)
):
    """更新营销群"""
    group = session.get(FunnelGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Funnel group not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


@router.delete("/{group_id}")
def delete_funnel_group(
    group_id: int,
    session: Session = Depends(get_session)
):
    """删除营销群"""
    group = session.get(FunnelGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Funnel group not found")
    
    session.delete(group)
    session.commit()
    return {"success": True}


@router.get("/{group_id}/stats")
def get_funnel_group_stats(
    group_id: int,
    session: Session = Depends(get_session)
):
    """获取营销群统计"""
    group = session.get(FunnelGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Funnel group not found")
    
    return {
        "group": group,
        "stats": {
            "member_count": group.member_count,
            "today_joined": group.today_joined,
            "today_left": group.today_left,
            "net_growth": group.today_joined - group.today_left
        }
    }
