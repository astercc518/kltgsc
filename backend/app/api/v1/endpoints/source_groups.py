"""
流量源/猎场管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime

from app.core.db import get_session
from app.models.source_group import SourceGroup, SourceGroupCreate, SourceGroupUpdate, SourceGroupRead
from app.models.target_user import TargetUser

router = APIRouter()


@router.get("/", response_model=List[SourceGroupRead])
def get_source_groups(
    skip: int = 0,
    limit: int = 50,
    type: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取流量源列表"""
    query = select(SourceGroup)
    if type:
        query = query.where(SourceGroup.type == type)
    if status:
        query = query.where(SourceGroup.status == status)
    query = query.offset(skip).limit(limit).order_by(SourceGroup.created_at.desc())
    return session.exec(query).all()


@router.post("/", response_model=SourceGroupRead)
def create_source_group(
    source_group: SourceGroupCreate,
    session: Session = Depends(get_session)
):
    """添加流量源"""
    # 检查是否已存在
    existing = session.exec(
        select(SourceGroup).where(SourceGroup.link == source_group.link)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Source group already exists")
    
    db_group = SourceGroup(**source_group.dict())
    session.add(db_group)
    session.commit()
    session.refresh(db_group)
    return db_group


@router.post("/batch")
def create_source_groups_batch(
    links: List[str],
    type: str = "traffic",
    session: Session = Depends(get_session)
):
    """批量添加流量源"""
    created = 0
    skipped = 0
    
    for link in links:
        link = link.strip()
        if not link:
            continue
        
        existing = session.exec(
            select(SourceGroup).where(SourceGroup.link == link)
        ).first()
        
        if existing:
            skipped += 1
            continue
        
        db_group = SourceGroup(link=link, type=type)
        session.add(db_group)
        created += 1
    
    session.commit()
    return {"created": created, "skipped": skipped}


@router.get("/{group_id}", response_model=SourceGroupRead)
def get_source_group(
    group_id: int,
    session: Session = Depends(get_session)
):
    """获取流量源详情"""
    group = session.get(SourceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Source group not found")
    return group


@router.put("/{group_id}", response_model=SourceGroupRead)
def update_source_group(
    group_id: int,
    updates: SourceGroupUpdate,
    session: Session = Depends(get_session)
):
    """更新流量源"""
    group = session.get(SourceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Source group not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


@router.delete("/{group_id}")
def delete_source_group(
    group_id: int,
    session: Session = Depends(get_session)
):
    """删除流量源"""
    group = session.get(SourceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Source group not found")
    
    session.delete(group)
    session.commit()
    return {"success": True}


@router.get("/{group_id}/users", response_model=List)
def get_source_group_users(
    group_id: int,
    skip: int = 0,
    limit: int = 100,
    min_score: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """获取该流量源采集的用户"""
    group = session.get(SourceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Source group not found")
    
    query = select(TargetUser).where(TargetUser.source_group == group.link)
    if min_score:
        query = query.where(TargetUser.ai_score >= min_score)
    query = query.offset(skip).limit(limit).order_by(TargetUser.ai_score.desc())
    
    return session.exec(query).all()


@router.get("/stats/summary")
def get_source_groups_summary(
    session: Session = Depends(get_session)
):
    """获取流量源统计摘要"""
    groups = session.exec(select(SourceGroup)).all()
    
    by_type = {}
    for g in groups:
        if g.type not in by_type:
            by_type[g.type] = {"count": 0, "total_scraped": 0, "high_value": 0}
        by_type[g.type]["count"] += 1
        by_type[g.type]["total_scraped"] += g.total_scraped
        by_type[g.type]["high_value"] += g.high_value_count
    
    return {
        "total_groups": len(groups),
        "by_type": by_type
    }
