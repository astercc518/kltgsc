"""
AI 人设管理 API
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.ai_persona import AIPersona, AIPersonaCreate, AIPersonaUpdate, AIPersonaRead

router = APIRouter()


@router.get("/", response_model=List[AIPersonaRead])
def get_personas(
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session)
):
    """获取AI人设列表"""
    query = select(AIPersona).offset(skip).limit(limit).order_by(AIPersona.created_at.desc())
    return session.exec(query).all()


@router.post("/", response_model=AIPersonaRead)
def create_persona(
    persona: AIPersonaCreate,
    session: Session = Depends(get_session)
):
    """创建AI人设"""
    db_persona = AIPersona(**persona.dict())
    session.add(db_persona)
    session.commit()
    session.refresh(db_persona)
    return db_persona


@router.get("/{persona_id}", response_model=AIPersonaRead)
def get_persona(
    persona_id: int,
    session: Session = Depends(get_session)
):
    """获取AI人设详情"""
    persona = session.get(AIPersona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.put("/{persona_id}", response_model=AIPersonaRead)
def update_persona(
    persona_id: int,
    updates: AIPersonaUpdate,
    session: Session = Depends(get_session)
):
    """更新AI人设"""
    persona = session.get(AIPersona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(persona, key, value)
    
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona


@router.delete("/{persona_id}")
def delete_persona(
    persona_id: int,
    session: Session = Depends(get_session)
):
    """删除AI人设"""
    persona = session.get(AIPersona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    session.delete(persona)
    session.commit()
    return {"success": True}


@router.post("/init-defaults")
def init_default_personas(
    session: Session = Depends(get_session)
):
    """初始化默认人设"""
    defaults = [
        {
            "name": "金牌销售",
            "description": "专业的加密货币投资顾问，热情友好",
            "system_prompt": "你是一个专业的加密货币投资顾问，热情友好，善于倾听客户需求，引导客户了解产品优势。不要直接推销，先建立信任。使用中文回复，适当使用emoji。",
            "tone": "friendly"
        },
        {
            "name": "技术分析师",
            "description": "资深技术分析师，说话专业但不晦涩",
            "system_prompt": "你是一个资深的技术分析师，说话专业但不晦涩，善于用数据说话。偶尔分享盈利截图增加可信度。使用中文回复。",
            "tone": "professional"
        },
        {
            "name": "热心群友",
            "description": "群里的活跃用户，语气轻松随意",
            "system_prompt": "你是群里的活跃用户，经常分享自己的投资心得，语气轻松随意，会用emoji和网络用语。使用中文回复。",
            "tone": "casual"
        }
    ]
    
    created = 0
    for p in defaults:
        existing = session.exec(
            select(AIPersona).where(AIPersona.name == p["name"])
        ).first()
        if not existing:
            session.add(AIPersona(**p))
            created += 1
    
    session.commit()
    return {"created": created, "message": f"Created {created} default personas"}
