"""
AI 知识库管理 API
用于 RAG 对话支持
"""
import json
import os
import shutil
import tempfile
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime

from app.core.db import get_session
from app.models.knowledge_base import (
    KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead,
    CampaignKnowledgeLink
)
from app.models.account import Account
from app.models.group_message import GroupMessage
from app.models.scraping_task import ScrapingTask
from app.services.ai_engine import AIEngine
from sqlalchemy import func, Integer

logger = logging.getLogger(__name__)
router = APIRouter()

# 导入临时目录（容器内）
IMPORT_TMP_DIR = "/tmp/kb_imports"
ALLOWED_IMPORT_EXTS = {".pdf"}
MAX_IMPORT_BYTES = 50 * 1024 * 1024  # 50 MB


# ─────────── 群组采集（Phase 1）───────────
class ScrapeGroupsRequest(BaseModel):
    include_private: bool = True
    limit_per_chat: Optional[int] = None  # None = 全量
    chat_sleep_sec: float = 2.0


@router.post("/scrape/{account_id}")
def trigger_scrape_account_groups(
    account_id: int,
    body: ScrapeGroupsRequest,
    session: Session = Depends(get_session),
):
    """
    触发指定账号的群组+私聊消息全量采集。
    返回 scraping_task_id，用 GET /scrape/status/{id} 查询进度。
    """
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status not in ("active", "spam_block"):
        raise HTTPException(status_code=400, detail=f"Account status is {account.status}, must be active")

    # 创建 ScrapingTask 记录
    st = ScrapingTask(
        task_type="scrape_messages",
        status="pending",
        account_ids_json=json.dumps([account_id]),
        group_links_json="[]",
        result_json="{}",
    )
    session.add(st)
    session.commit()
    session.refresh(st)

    # 派发 Celery 任务
    from app.tasks.knowledge_tasks import scrape_account_groups
    celery_result = scrape_account_groups.delay(
        account_id=account_id,
        scraping_task_id=st.id,
        include_private=body.include_private,
        limit_per_chat=body.limit_per_chat,
        chat_sleep_sec=body.chat_sleep_sec,
    )
    st.celery_task_id = celery_result.id
    session.add(st)
    session.commit()

    return {
        "scraping_task_id": st.id,
        "celery_task_id": celery_result.id,
        "account_id": account_id,
        "phone": account.phone_number,
    }


@router.get("/scrape/status/{scraping_task_id}")
def get_scrape_status(
    scraping_task_id: int,
    session: Session = Depends(get_session),
):
    """查询采集任务进度"""
    st = session.get(ScrapingTask, scraping_task_id)
    if not st:
        raise HTTPException(status_code=404, detail="Scraping task not found")
    try:
        progress = json.loads(st.result_json) if st.result_json else {}
    except Exception:
        progress = {}
    return {
        "id": st.id,
        "status": st.status,
        "celery_task_id": st.celery_task_id,
        "created_at": st.created_at,
        "completed_at": st.completed_at,
        "error_message": st.error_message,
        "progress": progress,
    }


# ─────────── Q&A 抽取（Phase 2）───────────
class ExtractQARequest(BaseModel):
    chat_ids: Optional[List[int]] = None  # None = 全部
    window_size: int = 50
    concurrency: int = 3
    max_windows: Optional[int] = None  # None = 全量


@router.post("/extract-qa")
def trigger_extract_qa(
    body: ExtractQARequest,
    session: Session = Depends(get_session),
):
    """触发 Q&A 抽取任务，从 group_message 表抽 Q&A 写入 knowledge_base。"""
    st = ScrapingTask(
        task_type="extract_qa",
        status="pending",
        account_ids_json="[]",
        group_links_json=json.dumps(body.chat_ids or []),
        result_json="{}",
    )
    session.add(st)
    session.commit()
    session.refresh(st)

    from app.tasks.knowledge_tasks import extract_qa_from_messages
    celery_result = extract_qa_from_messages.delay(
        chat_ids=body.chat_ids,
        window_size=body.window_size,
        concurrency=body.concurrency,
        scraping_task_id=st.id,
        max_windows=body.max_windows,
    )
    st.celery_task_id = celery_result.id
    session.add(st)
    session.commit()
    return {"scraping_task_id": st.id, "celery_task_id": celery_result.id}


# ─────────── 文件批量导入（Phase 3）───────────
@router.post("/import/file")
async def import_knowledge_file(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """
    上传文档文件（MVP 仅 PDF），异步解析 + chunk + embedding + 入库。
    返回 Celery task_id；查询进度用 GET /import/status/{task_id}。
    """
    safe_filename = os.path.basename(file.filename or "")
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="无效的文件名")

    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in ALLOWED_IMPORT_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext}；MVP 仅支持 {sorted(ALLOWED_IMPORT_EXTS)}",
        )

    os.makedirs(IMPORT_TMP_DIR, exist_ok=True)
    # 用 mkstemp 防文件名碰撞
    fd, tmp_path = tempfile.mkstemp(
        prefix="kb_", suffix=ext, dir=IMPORT_TMP_DIR
    )
    try:
        with os.fdopen(fd, "wb") as out:
            total = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IMPORT_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件超过 {MAX_IMPORT_BYTES // 1024 // 1024} MB 上限",
                    )
                out.write(chunk)
    except HTTPException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

    from app.tasks.import_tasks import import_pdf_to_kb
    result = import_pdf_to_kb.delay(
        file_path=tmp_path,
        category=category,
        source_filename=safe_filename,
    )

    return {
        "task_id": result.id,
        "filename": safe_filename,
        "category": category,
        "queued": True,
    }


@router.get("/import/status/{task_id}")
def get_import_status(task_id: str):
    """查询 PDF 导入任务进度。"""
    from app.core.celery_app import celery_app
    async_result = celery_app.AsyncResult(task_id)
    payload = {
        "task_id": task_id,
        "state": async_result.state,
        "ready": async_result.ready(),
    }
    if async_result.ready():
        try:
            payload["result"] = async_result.result
        except Exception as e:
            payload["error"] = str(e)
    return payload


@router.get("/scrape/messages/stats")
def get_scraped_messages_stats(
    account_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """采集到的消息统计：按 chat 聚合"""
    q = select(
        GroupMessage.chat_id,
        GroupMessage.chat_title,
        GroupMessage.chat_type,
        func.count(GroupMessage.id).label("msg_count"),
        func.sum(func.cast(GroupMessage.qa_extracted, Integer)).label("extracted"),
    ).group_by(GroupMessage.chat_id, GroupMessage.chat_title, GroupMessage.chat_type)
    if account_id:
        q = q.where(GroupMessage.account_id == account_id)
    rows = session.exec(q).all()
    return [
        {
            "chat_id": r[0],
            "chat_title": r[1],
            "chat_type": r[2],
            "message_count": r[3],
            "qa_extracted": int(r[4] or 0),
        }
        for r in rows
    ]





class GenerateContentRequest(BaseModel):
    name: str
    description: str
    reference_material: Optional[str] = None


@router.post("/generate-content")
async def generate_knowledge_content(
    request: GenerateContentRequest,
    session: Session = Depends(get_session)
):
    """AI 自动生成知识库内容"""
    engine = AIEngine(session)
    content = await engine.generate_knowledge_content(
        name=request.name,
        description=request.description,
        reference_material=request.reference_material,
    )
    return {"content": content}


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
