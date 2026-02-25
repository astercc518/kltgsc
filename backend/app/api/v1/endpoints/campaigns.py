"""
战役/项目管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from datetime import datetime

from app.core.db import get_session
from app.models.campaign import Campaign, CampaignCreate, CampaignUpdate, CampaignRead
from app.models.send_task import SendTask
from app.models.funnel_group import FunnelGroup

router = APIRouter()


@router.get("/", response_model=List[CampaignRead])
def get_campaigns(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取战役列表"""
    query = select(Campaign)
    if status:
        query = query.where(Campaign.status == status)
    query = query.offset(skip).limit(limit).order_by(Campaign.created_at.desc())
    return session.exec(query).all()


@router.post("/", response_model=CampaignRead)
def create_campaign(
    campaign: CampaignCreate,
    session: Session = Depends(get_session)
):
    """创建战役"""
    db_campaign = Campaign(**campaign.dict())
    session.add(db_campaign)
    session.commit()
    session.refresh(db_campaign)
    return db_campaign


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: int,
    session: Session = Depends(get_session)
):
    """获取战役详情"""
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.put("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    updates: CampaignUpdate,
    session: Session = Depends(get_session)
):
    """更新战役"""
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)
    
    campaign.updated_at = datetime.utcnow()
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    session: Session = Depends(get_session)
):
    """删除战役"""
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    session.delete(campaign)
    session.commit()
    return {"success": True, "message": "Campaign deleted"}


@router.get("/{campaign_id}/dashboard")
def get_campaign_dashboard(
    campaign_id: int,
    session: Session = Depends(get_session)
):
    """获取战役数据大屏"""
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 获取关联的营销群
    funnel_groups = session.exec(
        select(FunnelGroup).where(FunnelGroup.campaign_id == campaign_id)
    ).all()
    
    # 计算转化率
    reply_rate = 0
    if campaign.total_messages_sent > 0:
        reply_rate = round(campaign.total_replies_received / campaign.total_messages_sent * 100, 2)
    
    conversion_rate = 0
    if campaign.total_replies_received > 0:
        conversion_rate = round(campaign.total_conversions / campaign.total_replies_received * 100, 2)
    
    return {
        "campaign": campaign,
        "funnel_groups": funnel_groups,
        "metrics": {
            "total_messages_sent": campaign.total_messages_sent,
            "total_replies_received": campaign.total_replies_received,
            "total_conversions": campaign.total_conversions,
            "reply_rate": reply_rate,
            "conversion_rate": conversion_rate
        }
    }
