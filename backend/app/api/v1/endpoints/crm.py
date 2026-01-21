from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.core.db import get_session
from app.models.lead import Lead, LeadCreate, LeadRead, LeadInteraction, LeadInteractionCreate, LeadInteractionRead
from app.models.account import Account
from app.services.telegram_client import send_message_with_client
from app.services.websocket_manager import manager

router = APIRouter()

# --- Leads ---

@router.get("/leads", response_model=List[LeadRead])
def get_leads(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """获取线索列表"""
    query = select(Lead)
    if status:
        query = query.where(Lead.status == status)
    
    # Sort by last interaction desc
    query = query.offset(skip).limit(limit).order_by(Lead.last_interaction_at.desc())
    return session.exec(query).all()

@router.get("/leads/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: int,
    session: Session = Depends(get_session)
):
    """获取单个线索详情"""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.put("/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: int,
    lead_update: dict = Body(...),
    session: Session = Depends(get_session)
):
    """更新线索信息"""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    for key, value in lead_update.items():
        if hasattr(lead, key):
            setattr(lead, key, value)
            
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead

@router.post("/leads/{lead_id}/send")
async def send_lead_message(
    lead_id: int,
    payload: dict = Body(...),
    session: Session = Depends(get_session)
):
    """向线索发送消息"""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="Content required")
        
    account = session.get(Account, lead.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    # Send via TG
    # Note: lead.username might be None, lead.phone might be None. 
    # Best way is to use lead.telegram_user_id if Pyrogram supports it (it usually does for users it has seen)
    # Or username if available.
    target = lead.username or lead.telegram_user_id
    
    success, msg = await send_message_with_client(account, str(target), content, db_session=session)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
        
    # Record interaction
    interaction = LeadInteraction(
        lead_id=lead.id,
        direction="outbound",
        content=content,
        created_at=datetime.utcnow()
    )
    lead.last_interaction_at = datetime.utcnow()
    lead.status = "contacted"
    
    session.add(interaction)
    session.add(lead)
    session.commit()
    
    # Broadcast update
    await manager.broadcast({
        "type": "new_message",
        "lead_id": lead.id,
        "message": interaction.dict() # pydantic v1, or model_dump in v2
    })
    
    return {"status": "success", "message": "Sent"}
