from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.core.db import get_session
from app.api.deps import get_current_user, get_current_sales_or_admin
from app.models.lead import Lead, LeadCreate, LeadRead, LeadInteraction, LeadInteractionCreate, LeadInteractionRead
from app.models.account import Account
from app.models.user import User
from app.services.telegram_client import send_message_with_client
from app.services.websocket_manager import manager

router = APIRouter()


# ── 接管相关请求/响应 ──
class AIConfigRequest(BaseModel):
    ai_enabled: bool


class ClaimResponse(BaseModel):
    lead: LeadRead
    assigned_to_username: Optional[str] = None

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


# ─────────── 销售接管 / AI 副驾驶（Phase 5）───────────

def _serialize_lead(lead: Lead) -> LeadRead:
    return LeadRead.model_validate(lead, from_attributes=True)


@router.post("/leads/{lead_id}/claim", response_model=ClaimResponse)
async def claim_lead(
    lead_id: int,
    current_user: User = Depends(get_current_sales_or_admin),
    session: Session = Depends(get_session),
):
    """
    销售/管理员认领线索：
      - 写入 assigned_to_user_id + claimed_at
      - 关闭 AI 自动发送（ai_enabled=False），切换到副驾驶模式
      - 若已被他人认领且不是 admin/superuser，拒绝
    """
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if (
        lead.assigned_to_user_id is not None
        and lead.assigned_to_user_id != current_user.id
        and not current_user.is_superuser
        and current_user.role != "admin"
    ):
        owner = session.get(User, lead.assigned_to_user_id)
        raise HTTPException(
            status_code=409,
            detail=f"线索已被 {owner.username if owner else '其他销售'} 认领",
        )

    lead.assigned_to_user_id = current_user.id
    lead.claimed_at = datetime.utcnow()
    lead.ai_enabled = False
    session.add(lead)
    session.commit()
    session.refresh(lead)

    await manager.broadcast({
        "type": "lead_claimed",
        "lead_id": lead.id,
        "assigned_to_user_id": current_user.id,
        "assigned_to_username": current_user.username,
    })

    return ClaimResponse(
        lead=_serialize_lead(lead),
        assigned_to_username=current_user.username,
    )


@router.post("/leads/{lead_id}/release", response_model=LeadRead)
async def release_lead(
    lead_id: int,
    current_user: User = Depends(get_current_sales_or_admin),
    session: Session = Depends(get_session),
):
    """
    释放线索：清空 assigned_to_user_id，重新开启 AI 自动回复。
    只有认领人本人或 admin 可释放。
    """
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if (
        lead.assigned_to_user_id is not None
        and lead.assigned_to_user_id != current_user.id
        and not current_user.is_superuser
        and current_user.role != "admin"
    ):
        raise HTTPException(status_code=403, detail="无权释放他人认领的线索")

    lead.assigned_to_user_id = None
    lead.claimed_at = None
    lead.ai_enabled = True
    session.add(lead)
    session.commit()
    session.refresh(lead)

    await manager.broadcast({
        "type": "lead_released",
        "lead_id": lead.id,
    })

    return _serialize_lead(lead)


@router.put("/leads/{lead_id}/ai-config", response_model=LeadRead)
async def update_lead_ai_config(
    lead_id: int,
    body: AIConfigRequest,
    current_user: User = Depends(get_current_sales_or_admin),
    session: Session = Depends(get_session),
):
    """单独切换 ai_enabled。接管中的线索，销售可手动开关副驾驶。"""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if (
        lead.assigned_to_user_id is not None
        and lead.assigned_to_user_id != current_user.id
        and not current_user.is_superuser
        and current_user.role != "admin"
    ):
        raise HTTPException(status_code=403, detail="无权修改他人线索")

    lead.ai_enabled = body.ai_enabled
    session.add(lead)
    session.commit()
    session.refresh(lead)

    await manager.broadcast({
        "type": "lead_ai_config",
        "lead_id": lead.id,
        "ai_enabled": lead.ai_enabled,
    })

    return _serialize_lead(lead)


@router.post("/leads/{lead_id}/regenerate-draft", response_model=LeadRead)
async def regenerate_lead_draft(
    lead_id: int,
    current_user: User = Depends(get_current_sales_or_admin),
    session: Session = Depends(get_session),
):
    """
    强制让 AI 重新基于最近对话 + KB 生成草稿。
    草稿写到 lead.ai_draft 并通过 WS 广播。
    """
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 取最近一条客户来消息作为生成依据
    from app.models.chat_history import ChatHistory
    last_inbound = session.exec(
        select(ChatHistory)
        .where(ChatHistory.account_id == lead.account_id)
        .where(ChatHistory.target_user_id == lead.telegram_user_id)
        .where(ChatHistory.role == "user")
        .order_by(ChatHistory.created_at.desc())
        .limit(1)
    ).first()

    if not last_inbound:
        raise HTTPException(
            status_code=400,
            detail="客户暂无来信，无法生成草稿",
        )

    from app.services.ai_reply_service import AIReplyService
    account = session.get(Account, lead.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    svc = AIReplyService(session)
    draft = await svc._generate_reply(
        account,
        last_inbound.content,
        lead.telegram_user_id,
        lead.first_name or "",
        lead.username,
    )

    lead.ai_draft = draft or ""
    session.add(lead)
    session.commit()
    session.refresh(lead)

    await manager.broadcast({
        "type": "ai_draft",
        "lead_id": lead.id,
        "draft": lead.ai_draft,
    })

    return _serialize_lead(lead)
