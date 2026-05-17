import logging
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select
from pydantic import BaseModel
from app.core.db import get_session
from app.models.keyword_monitor import KeywordMonitor, KeywordMonitorCreate, KeywordMonitorRead, KeywordMonitorUpdate, KeywordHit, KeywordHitRead
from app.services.keyword_monitor_service import KeywordMonitorService
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# AI 关键词联想 & 语义判别 接口
# ============================================

class KeywordSuggestionRequest(BaseModel):
    seed_keyword: str = None  # 种子关键词
    scenario_description: str = None  # 业务场景描述

class SemanticMatchRequest(BaseModel):
    scenario_description: str  # 业务场景描述
    message_content: str  # 待判别的消息内容
    context_messages: List[str] = []  # 上下文消息 (可选)


@router.post("/suggest-keywords")
async def suggest_keywords(
    request: KeywordSuggestionRequest,
    session: Session = Depends(get_session)
):
    """
    AI 关键词联想：根据种子词或场景描述，自动生成相关关键词列表
    用于方案A的Level1粗筛
    """
    llm = LLMService(session)
    
    if request.scenario_description:
        # 基于场景描述生成
        prompt = f"""
你是一个即时通讯软件（Telegram）的营销专家。
用户想监控以下业务场景的相关讨论：

【业务场景】
{request.scenario_description}

请分析这个场景，列出用户在聊天中可能使用的 15-25 个相关高频词、同义词、缩写、口语表达或竞品词。

要求：
1. 只输出词语，不要解释
2. 用英文逗号分隔
3. 排除过于通用的词（如"的"、"是"、"什么"）
4. 侧重于商业意图、用户痛点、购买信号
5. 包含中英文、缩写、口语化表达

示例格式：价格,多少钱,怎么买,购买,下单,cost,price,靠谱吗,推荐
"""
    elif request.seed_keyword:
        # 基于种子词扩展
        prompt = f"""
你是一个即时通讯软件（Telegram）的营销专家。
用户想监控关于 "{request.seed_keyword}" 的讨论。
请联想并列出 15-25 个用户可能会在聊天中使用的相关高频词、同义词、缩写、口语或竞品词。

要求：
1. 只输出词语，不要解释
2. 用英文逗号分隔
3. 排除过于通用的词
4. 侧重于商业意图或用户痛点
5. 包含中英文表达

示例：如果种子词是"VPN"，输出：翻墙,梯子,节点,科学上网,v2ray,clash,加速器,proxy,代理,机场
"""
    else:
        raise HTTPException(status_code=400, detail="请提供种子关键词或业务场景描述")
    
    try:
        response = await llm.get_response(prompt, system_prompt="你是一个关键词扩充助手，只输出关键词列表。")
        if not response:
            raise HTTPException(status_code=500, detail="AI 服务暂时不可用")
        
        # 清理结果
        keywords = [k.strip() for k in response.replace('\n', ',').replace('，', ',').split(',') if k.strip() and len(k.strip()) > 1]
        # 去重
        keywords = list(dict.fromkeys(keywords))
        
        return {"keywords": keywords[:25], "count": len(keywords[:25])}
    except Exception as e:
        logger.error(f"Keyword suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI 服务繁忙: {str(e)}")


@router.post("/semantic-match")
async def semantic_match(
    request: SemanticMatchRequest,
    session: Session = Depends(get_session)
):
    """
    语义匹配判别 (Level2精判)：判断消息内容是否符合目标业务场景
    返回匹配结果和置信度
    """
    llm = LLMService(session)
    
    # 构建上下文
    context_str = ""
    if request.context_messages:
        context_str = "\n".join([f"- {msg}" for msg in request.context_messages[-5:]])
        context_str = f"\n【上下文消息】\n{context_str}\n"
    
    prompt = f"""
你是一个精准的意图判别助手。请判断以下消息是否符合目标业务场景。

【目标业务场景】
{request.scenario_description}

{context_str}
【待判别消息】
{request.message_content}

请分析：
1. 这条消息是否表达了与目标场景相关的需求或意图？
2. 考虑上下文（如果有），判断用户的真实意图。
3. 区分"真需求"和"随口提及"或"否定句"。

请严格按以下 JSON 格式输出：
{{"match": true/false, "confidence": 0-100, "reason": "简短理由"}}
"""
    
    try:
        response = await llm.get_response(prompt, system_prompt="你是一个意图判别助手，只输出JSON格式结果。")
        if not response:
            return {"match": False, "confidence": 0, "reason": "AI 服务不可用"}
        
        # 解析 JSON
        try:
            # 尝试提取 JSON 部分
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                return {"match": False, "confidence": 0, "reason": "解析失败", "raw": response}
        except json.JSONDecodeError:
            return {"match": False, "confidence": 0, "reason": "JSON解析失败", "raw": response}
            
    except Exception as e:
        logger.error(f"Semantic match failed: {e}")
        return {"match": False, "confidence": 0, "reason": str(e)}

@router.post("/", response_model=KeywordMonitorRead)
def create_monitor(
    monitor_create: KeywordMonitorCreate,
    session: Session = Depends(get_session)
):
    service = KeywordMonitorService(session)
    return service.create_monitor(monitor_create)

@router.get("/", response_model=List[KeywordMonitorRead])
def get_monitors(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    service = KeywordMonitorService(session)
    return service.get_monitors(skip=skip, limit=limit)

@router.put("/{monitor_id}", response_model=KeywordMonitorRead)
def update_monitor(
    monitor_id: int,
    monitor_update: KeywordMonitorUpdate,
    session: Session = Depends(get_session)
):
    service = KeywordMonitorService(session)
    monitor = service.update_monitor(monitor_id, monitor_update)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor

@router.delete("/{monitor_id}")
def delete_monitor(
    monitor_id: int,
    session: Session = Depends(get_session)
):
    service = KeywordMonitorService(session)
    success = service.delete_monitor(monitor_id)
    if not success:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {"status": "success"}

@router.get("/hits", response_model=List[KeywordHitRead])
def get_hits(
    skip: int = 0,
    limit: int = 50,
    status: str = Query(None),
    session: Session = Depends(get_session)
):
    service = KeywordMonitorService(session)
    return service.get_hits(skip=skip, limit=limit, status=status)


# ============================================
# 竞品群实时截流 API
# ============================================

from app.services.intercept_service import InterceptService


class NewMemberEvent(BaseModel):
    source_group_id: int
    user_id: int
    username: str = None
    first_name: str = None
    bio: str = None


@router.post("/intercept/new-member")
async def handle_new_member(
    event: NewMemberEvent,
    session: Session = Depends(get_session)
):
    """
    处理竞品群新成员加入事件
    
    这个接口由监听服务调用，当检测到竞品群有新成员加入时触发
    """
    service = InterceptService(session)
    result = await service.process_new_member(
        source_group_id=event.source_group_id,
        user_id=event.user_id,
        username=event.username,
        first_name=event.first_name,
        bio=event.bio
    )
    return result


@router.get("/intercept/stats")
def get_intercept_stats(
    session: Session = Depends(get_session)
):
    """获取截流统计数据"""
    service = InterceptService(session)
    return service.get_intercept_stats()


@router.post("/intercept/test")
async def test_intercept(
    source_group_id: int = Query(...),
    session: Session = Depends(get_session)
):
    """
    测试截流功能（模拟新成员加入）
    """
    import random
    
    service = InterceptService(session)
    
    # 模拟用户数据
    test_user_id = random.randint(1000000000, 9999999999)
    test_username = f"test_user_{random.randint(1000, 9999)}"
    test_bio = random.choice([
        "Crypto enthusiast | DeFi lover",
        "投资爱好者，专注区块链",
        "Trading since 2020",
        None
    ])
    
    result = await service.process_new_member(
        source_group_id=source_group_id,
        user_id=test_user_id,
        username=test_username,
        first_name="Test",
        bio=test_bio
    )
    
    return {
        "test_data": {
            "user_id": test_user_id,
            "username": test_username,
            "bio": test_bio
        },
        "result": result
    }


# ============================================================
# 自由发言 API
# ============================================================

# ============================================================
# Live-Chat 群管理 API（ConversationDirector）
# ============================================================

class LiveChatGroupRequest(BaseModel):
    group_id: str   # Telegram chat_id，如 "-5276158188"


@router.post("/live-chat/groups")
def enable_live_chat_group(request: LiveChatGroupRequest):
    """为指定群启用 ConversationDirector 动态对话模式。"""
    from app.services.conversation_director import ConversationDirector
    ConversationDirector().enable_group(request.group_id)
    return {"success": True, "group_id": request.group_id, "action": "enabled"}


@router.delete("/live-chat/groups/{group_id:path}")
def disable_live_chat_group(group_id: str):
    """关闭指定群的动态对话模式。"""
    from app.services.conversation_director import ConversationDirector
    ConversationDirector().disable_group(group_id)
    return {"success": True, "group_id": group_id, "action": "disabled"}


@router.get("/live-chat/groups")
def list_live_chat_groups():
    """列出已启用动态对话的群。"""
    from app.services.conversation_director import ConversationDirector
    groups = ConversationDirector().list_groups()
    return {"groups": groups, "count": len(groups)}


class FreeChatRequest(BaseModel):
    chat_id: str                          # 目标群 chat_id（如 "-5276158188"）
    topic: str                            # 话题，给 AI 生成内容用
    account_ids: Optional[List[int]] = None  # None = 全部 active 账号
    turns_per_account: int = 1           # 每个账号发几轮


@router.post("/free-chat")
def trigger_free_chat(
    request: FreeChatRequest,
    session: Session = Depends(get_session),
):
    """
    触发多账号自由发言：所有指定账号按 AI 人设生成消息，随机间隔发送到目标群。
    """
    from app.models.account import Account
    from app.tasks.monitor_tasks import execute_free_conversation

    if request.account_ids:
        account_ids = request.account_ids
    else:
        accounts = session.exec(
            select(Account).where(Account.status == "active")
        ).all()
        account_ids = [a.id for a in accounts if a.ai_persona_id is not None]

    if not account_ids:
        raise HTTPException(status_code=400, detail="No active accounts with personas found")

    execute_free_conversation.delay(
        account_ids,
        request.chat_id,
        request.topic,
        request.turns_per_account,
    )

    return {
        "success": True,
        "message": f"已调度 {len(account_ids)} 个账号发言，话题：{request.topic}",
        "account_ids": account_ids,
        "turns_per_account": request.turns_per_account,
    }
