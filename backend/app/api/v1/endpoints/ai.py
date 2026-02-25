from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.core.db import get_session
from app.services.llm import LLMService
from app.models.account import Account
from app.models.ai_config import AIConfig, AIConfigCreate, AIConfigUpdate, AIConfigResponse
from app.worker import check_auto_reply_task

router = APIRouter()


# ============ AI 配置管理 API ============

@router.get("/configs", response_model=List[AIConfigResponse])
async def get_ai_configs(
    active_only: bool = Query(False, description="仅返回启用的配置"),
    session: Session = Depends(get_session)
):
    """获取所有AI配置列表"""
    query = select(AIConfig)
    if active_only:
        query = query.where(AIConfig.is_active == True)
    query = query.order_by(AIConfig.is_default.desc(), AIConfig.created_at.desc())
    configs = session.exec(query).all()
    
    # 转换为响应模型
    return [
        AIConfigResponse(
            id=c.id,
            name=c.name,
            provider=c.provider,
            base_url=c.base_url,
            model=c.model,
            is_default=c.is_default,
            is_active=c.is_active,
            created_at=c.created_at,
            updated_at=c.updated_at,
            has_api_key=bool(c.api_key)
        )
        for c in configs
    ]


@router.get("/configs/{config_id}", response_model=AIConfigResponse)
async def get_ai_config(
    config_id: int,
    session: Session = Depends(get_session)
):
    """获取单个AI配置"""
    config = session.get(AIConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="AI配置不存在")
    
    return AIConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        is_default=config.is_default,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        has_api_key=bool(config.api_key)
    )


@router.post("/configs", response_model=AIConfigResponse)
async def create_ai_config(
    data: AIConfigCreate,
    session: Session = Depends(get_session)
):
    """创建新的AI配置"""
    # 如果设为默认，先取消其他默认
    if data.is_default:
        existing_defaults = session.exec(
            select(AIConfig).where(AIConfig.is_default == True)
        ).all()
        for c in existing_defaults:
            c.is_default = False
            session.add(c)
    
    config = AIConfig(
        name=data.name,
        provider=data.provider,
        api_key=data.api_key,
        base_url=data.base_url,
        model=data.model,
        is_default=data.is_default,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    
    return AIConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        is_default=config.is_default,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        has_api_key=bool(config.api_key)
    )


@router.put("/configs/{config_id}", response_model=AIConfigResponse)
async def update_ai_config(
    config_id: int,
    data: AIConfigUpdate,
    session: Session = Depends(get_session)
):
    """更新AI配置"""
    config = session.get(AIConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="AI配置不存在")
    
    # 如果设为默认，先取消其他默认
    if data.is_default:
        existing_defaults = session.exec(
            select(AIConfig).where(AIConfig.is_default == True).where(AIConfig.id != config_id)
        ).all()
        for c in existing_defaults:
            c.is_default = False
            session.add(c)
    
    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    
    config.updated_at = datetime.utcnow()
    session.add(config)
    session.commit()
    session.refresh(config)
    
    return AIConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        is_default=config.is_default,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        has_api_key=bool(config.api_key)
    )


@router.delete("/configs/{config_id}")
async def delete_ai_config(
    config_id: int,
    session: Session = Depends(get_session)
):
    """删除AI配置"""
    config = session.get(AIConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="AI配置不存在")
    
    session.delete(config)
    session.commit()
    
    return {"message": "AI配置已删除", "id": config_id}


@router.put("/configs/{config_id}/default")
async def set_default_ai_config(
    config_id: int,
    session: Session = Depends(get_session)
):
    """设置AI配置为默认"""
    config = session.get(AIConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="AI配置不存在")
    
    # 取消其他默认
    existing_defaults = session.exec(
        select(AIConfig).where(AIConfig.is_default == True)
    ).all()
    for c in existing_defaults:
        c.is_default = False
        session.add(c)
    
    # 设置新默认
    config.is_default = True
    config.updated_at = datetime.utcnow()
    session.add(config)
    session.commit()
    
    return {"message": "已设置为默认配置", "id": config_id}


@router.post("/configs/{config_id}/test")
async def test_ai_config_connection(
    config_id: int,
    session: Session = Depends(get_session)
):
    """测试指定AI配置的连接"""
    config = session.get(AIConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="AI配置不存在")
    
    # 使用指定配置创建 LLMService
    llm = LLMService(session, config_id=config_id)
    success = await llm.test_connection()
    
    if not success:
        return {"status": "failed", "message": "连接失败", "config_id": config_id}
    return {"status": "success", "message": "连接成功", "config_id": config_id}


# ============ 原有的测试和触发 API ============

@router.get("/test_connection")
async def test_ai_connection(
    session: Session = Depends(get_session)
):
    """测试默认 LLM 连接（兼容旧接口）"""
    llm = LLMService(session)
    success = await llm.test_connection()
    if not success:
        return {"status": "failed", "message": "Connection failed"}
    return {"status": "success", "message": "Connection successful"}


@router.post("/trigger_auto_reply")
async def trigger_auto_reply(
    account_ids: List[int] = Query(None),
    session: Session = Depends(get_session)
):
    """手动触发账号的自动回复检查"""
    if not account_ids:
        # If no IDs provided, check all active accounts with auto_reply enabled
        accounts = session.exec(
            select(Account)
            .where(Account.status == "active")
            .where(Account.auto_reply == True)
        ).all()
        account_ids = [a.id for a in accounts]
    
    if not account_ids:
        return {"message": "No accounts found for auto-reply check", "task_ids": []}
        
    task_ids = []
    for aid in account_ids:
        task = check_auto_reply_task.delay(aid)
        task_ids.append(task.id)
        
    return {
        "message": f"Triggered check for {len(task_ids)} accounts", 
        "task_ids": task_ids
    }


# ============ AI Engine 高级功能 ============

from pydantic import BaseModel
from app.services.ai_engine import AIEngine


class UserAnalyzeRequest(BaseModel):
    username: str
    bio: Optional[str] = None
    messages: Optional[List[str]] = None


class GroupAnalyzeRequest(BaseModel):
    group_name: str
    messages: List[str]


class OpenerGenerateRequest(BaseModel):
    user_summary: str
    persona_id: Optional[int] = None
    tone: str = "friendly"


class ReplyGenerateRequest(BaseModel):
    conversation: List[dict]
    persona_id: Optional[int] = None
    knowledge: Optional[str] = None


class ScriptGenerateRequest(BaseModel):
    topic: str
    roles: List[dict]
    duration_minutes: int = 5


class ContentRewriteRequest(BaseModel):
    content: str
    count: int = 5


@router.post("/engine/analyze-user")
async def analyze_user(
    request: UserAnalyzeRequest,
    session: Session = Depends(get_session)
):
    """AI 分析用户画像"""
    engine = AIEngine(session)
    result = await engine.analyze_user(
        username=request.username,
        bio=request.bio,
        messages=request.messages
    )
    return {
        "score": result.score,
        "tags": result.tags,
        "is_bot": result.is_bot,
        "is_advertiser": result.is_advertiser,
        "interest_keywords": result.interest_keywords,
        "summary": result.summary
    }


@router.post("/engine/analyze-group")
async def analyze_group(
    request: GroupAnalyzeRequest,
    session: Session = Depends(get_session)
):
    """AI 分析群组价值"""
    engine = AIEngine(session)
    result = await engine.analyze_group(
        group_name=request.group_name,
        messages=request.messages
    )
    return {
        "score": result.score,
        "topics": result.topics,
        "spam_ratio": result.spam_ratio,
        "best_time": result.best_time,
        "recommendation": result.recommendation
    }


@router.post("/engine/generate-opener")
async def generate_opener(
    request: OpenerGenerateRequest,
    session: Session = Depends(get_session)
):
    """AI 生成定制化开场白"""
    engine = AIEngine(session)
    opener = await engine.generate_opener(
        user_summary=request.user_summary,
        persona_id=request.persona_id,
        tone=request.tone
    )
    return {"opener": opener}


@router.post("/engine/generate-reply")
async def generate_reply(
    request: ReplyGenerateRequest,
    session: Session = Depends(get_session)
):
    """AI 生成智能回复"""
    engine = AIEngine(session)
    reply = await engine.generate_reply(
        conversation=request.conversation,
        persona_id=request.persona_id,
        knowledge=request.knowledge
    )
    return {"reply": reply}


@router.post("/engine/generate-script")
async def generate_script(
    request: ScriptGenerateRequest,
    session: Session = Depends(get_session)
):
    """AI 生成炒群剧本"""
    engine = AIEngine(session)
    script = await engine.generate_script(
        topic=request.topic,
        roles=request.roles,
        duration_minutes=request.duration_minutes
    )
    return {"script": script, "message_count": len(script)}


@router.post("/engine/rewrite")
async def rewrite_content(
    request: ContentRewriteRequest,
    session: Session = Depends(get_session)
):
    """AI 生成内容变体"""
    engine = AIEngine(session)
    variants = await engine.rewrite_content(
        content=request.content,
        count=request.count
    )
    return {"variants": variants, "count": len(variants)}
