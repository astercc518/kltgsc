"""
AI 知识库管理 API
用于 RAG 对话支持
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime

from app.core.db import get_session
from app.models.knowledge_base import (
    KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead,
    CampaignKnowledgeLink
)

router = APIRouter()


@router.get("/", response_model=List[KnowledgeBaseRead])
def get_knowledge_bases(
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session)
):
    """获取知识库列表"""
    query = select(KnowledgeBase).offset(skip).limit(limit).order_by(KnowledgeBase.updated_at.desc())
    return session.exec(query).all()


@router.post("/", response_model=KnowledgeBaseRead)
def create_knowledge_base(
    kb: KnowledgeBaseCreate,
    session: Session = Depends(get_session)
):
    """创建知识库"""
    db_kb = KnowledgeBase(**kb.dict())
    session.add(db_kb)
    session.commit()
    session.refresh(db_kb)
    return db_kb


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    kb_id: int,
    session: Session = Depends(get_session)
):
    """获取知识库详情"""
    kb = session.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


@router.put("/{kb_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    kb_id: int,
    updates: KnowledgeBaseUpdate,
    session: Session = Depends(get_session)
):
    """更新知识库"""
    kb = session.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(kb, key, value)
    
    kb.updated_at = datetime.utcnow()
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return kb


@router.delete("/{kb_id}")
def delete_knowledge_base(
    kb_id: int,
    session: Session = Depends(get_session)
):
    """删除知识库"""
    kb = session.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 先删除关联
    links = session.exec(
        select(CampaignKnowledgeLink).where(CampaignKnowledgeLink.knowledge_base_id == kb_id)
    ).all()
    for link in links:
        session.delete(link)
    
    session.delete(kb)
    session.commit()
    return {"success": True}


@router.post("/{kb_id}/link-campaign/{campaign_id}")
def link_knowledge_base_to_campaign(
    kb_id: int,
    campaign_id: int,
    session: Session = Depends(get_session)
):
    """关联知识库到战役"""
    # 检查是否已存在
    existing = session.exec(
        select(CampaignKnowledgeLink).where(
            CampaignKnowledgeLink.knowledge_base_id == kb_id,
            CampaignKnowledgeLink.campaign_id == campaign_id
        )
    ).first()
    
    if existing:
        return {"message": "Already linked"}
    
    link = CampaignKnowledgeLink(campaign_id=campaign_id, knowledge_base_id=kb_id)
    session.add(link)
    session.commit()
    return {"success": True}


@router.delete("/{kb_id}/unlink-campaign/{campaign_id}")
def unlink_knowledge_base_from_campaign(
    kb_id: int,
    campaign_id: int,
    session: Session = Depends(get_session)
):
    """取消知识库与战役的关联"""
    link = session.exec(
        select(CampaignKnowledgeLink).where(
            CampaignKnowledgeLink.knowledge_base_id == kb_id,
            CampaignKnowledgeLink.campaign_id == campaign_id
        )
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    session.delete(link)
    session.commit()
    return {"success": True}


@router.get("/{kb_id}/campaigns")
def get_linked_campaigns(
    kb_id: int,
    session: Session = Depends(get_session)
):
    """获取知识库关联的战役列表"""
    from app.models.campaign import Campaign
    
    links = session.exec(
        select(CampaignKnowledgeLink).where(CampaignKnowledgeLink.knowledge_base_id == kb_id)
    ).all()
    
    campaign_ids = [link.campaign_id for link in links]
    campaigns = []
    for cid in campaign_ids:
        c = session.get(Campaign, cid)
        if c:
            campaigns.append({"id": c.id, "name": c.name, "status": c.status})
    
    return campaigns


@router.get("/search/content")
def search_knowledge_bases(
    query: str,
    limit: int = 5,
    session: Session = Depends(get_session)
):
    """搜索知识库内容（简单文本匹配，后续可升级为向量搜索）"""
    kbs = session.exec(
        select(KnowledgeBase).where(
            KnowledgeBase.content.contains(query)
        ).limit(limit)
    ).all()
    
    results = []
    for kb in kbs:
        # 找到包含关键词的段落
        content = kb.content
        idx = content.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(content), idx + len(query) + 100)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
        else:
            snippet = content[:200] + "..." if len(content) > 200 else content
        
        results.append({
            "id": kb.id,
            "name": kb.name,
            "snippet": snippet
        })
    
    return results
