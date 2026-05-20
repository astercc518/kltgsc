"""
Epic 4.1 — Customer-scoped KB management.

Lets paying customers:
  • POST   /customer/knowledge-bases          create a single KB entry
  • PATCH  /customer/knowledge-bases/{id}     edit one (re-embeds if content changed)
  • DELETE /customer/knowledge-bases/{id}     delete one
  • POST   /customer/knowledge-bases/upload   upload PDF/DOCX/TXT/MD (chunked)

Existing GET endpoints from customer_resources.py stay as-is (list / view).
All writes are tenant-scoped: a customer can only touch rows where
customer_id == self.id; system-owned (NULL) entries are read-only to them.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps_customer import get_active_customer
from app.core.db import get_session
from app.models.customer import Customer
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseRead
from app.services.embedding_service import EmbeddingService
from app.services.kb_upload_service import (
    KBUploadError, SUPPORTED_EXTENSIONS, upload_kb_file,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class KBCreateRequest(BaseModel):
    name: str
    content: str
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None


class KBUpdateRequest(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None


class UploadResponse(BaseModel):
    name: str
    total_chunks: int
    embedded_chunks: int
    extension: str


def _embed_safely(session: Session, text: str) -> Optional[list[float]]:
    """Same approach as industry_kb_service — sync wrapper with timeout."""
    if not text or not text.strip():
        return None
    try:
        es = EmbeddingService(session)
        if not es.is_configured():
            return None
        return asyncio.run(
            asyncio.wait_for(es.embed(text, source="kb_customer_write"), timeout=15.0)
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("KB embed on write failed: %r", e)
        return None


@router.post("/", response_model=KnowledgeBaseRead, status_code=201)
def create_kb(
    payload: KBCreateRequest,
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Create a new KB entry under the customer."""
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="content cannot be empty")
    emb = _embed_safely(session, payload.content)
    kb = KnowledgeBase(
        name=payload.name,
        description=payload.description,
        content=payload.content,
        source_type="manual",
        category=payload.category or "custom",
        language=payload.language,
        customer_id=customer.id,
        embedding=emb,
    )
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return KnowledgeBaseRead.model_validate(kb.model_dump())


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_kb(
    kb_id: int,
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    kb = session.get(KnowledgeBase, kb_id)
    if not kb or kb.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="KB not found")
    return KnowledgeBaseRead.model_validate(kb.model_dump())


@router.patch("/{kb_id}", response_model=KnowledgeBaseRead)
def update_kb(
    kb_id: int,
    payload: KBUpdateRequest,
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Update KB entry. If `content` changes, re-embed."""
    kb = session.get(KnowledgeBase, kb_id)
    if not kb or kb.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="KB not found")

    changes = payload.model_dump(exclude_unset=True)
    content_changed = "content" in changes and changes["content"] != kb.content

    for field, value in changes.items():
        setattr(kb, field, value)

    if content_changed:
        kb.embedding = _embed_safely(session, kb.content)

    from datetime import datetime
    kb.updated_at = datetime.utcnow()
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return KnowledgeBaseRead.model_validate(kb.model_dump())


@router.delete("/{kb_id}", status_code=204)
def delete_kb(
    kb_id: int,
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> None:
    kb = session.get(KnowledgeBase, kb_id)
    if not kb or kb.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="KB not found")
    session.delete(kb)
    session.commit()


@router.post("/upload", response_model=UploadResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Upload a document; we parse + chunk + embed + insert as customer KB rows.

    Supported types: PDF / DOCX / TXT / MD. Max 20 MB. Up to 200 chunks per file.

    Billing: feature `kb_file_upload`, unit = MB (rounded up). Pre-checks that
    customer has feature enabled + sufficient balance before reading file.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    data = file.file.read()

    # Feature billing pre-flight (rounded-up MB)
    import math
    from app.services import feature_billing as fb
    from app.services.wallet_service import InsufficientBalanceError
    units_mb = max(1, math.ceil(len(data) / (1024 * 1024)))
    try:
        fb.check_can_afford(session, customer.id, 'kb_file_upload', units_mb)
    except fb.FeatureNotEnabledError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=402, detail=str(e))

    try:
        result = upload_kb_file(
            session, customer,
            filename=file.filename, data=data,
            category=category, name=name,
        )
    except KBUploadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Charge AFTER successful upload (idempotency key = customer+filename+size+timestamp).
    # On charge failure (very unlikely after pre-flight), log but don't fail the upload.
    from datetime import datetime as _dt
    try:
        fb.charge(
            session,
            customer_id=customer.id,
            slug='kb_file_upload',
            units=units_mb,
            idempotency_key=f'feat:kb_file_upload:{customer.id}:{file.filename}:{len(data)}:{int(_dt.utcnow().timestamp())}',
            description=f'KB 文件上传 {file.filename} × {units_mb} MB',
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"kb_file_upload post-upload charge failed for customer {customer.id}: {e}"
        )

    return UploadResponse(
        name=result.name,
        total_chunks=result.total_chunks,
        embedded_chunks=result.embedded_chunks,
        extension=result.extension,
    )


@router.get("/_meta/supported-types")
def supported_types() -> dict:
    """For the portal's upload UI to know which extensions are allowed."""
    return {
        "extensions": sorted(SUPPORTED_EXTENSIONS),
        "max_bytes": 20 * 1024 * 1024,
    }


# ──────────────────────────────────────────────────────────────────────────
# Epic 5.1 — Import chat history from main account
# ──────────────────────────────────────────────────────────────────────────

from datetime import datetime, timedelta


class ImportHistoryRequest(BaseModel):
    # ISO date strings (frontend RangePicker output). Default: last 30 days.
    since: Optional[str] = None        # e.g. "2026-04-18T00:00:00"
    until: Optional[str] = None
    dialog_types: Optional[list[str]] = None  # ['private','group','supergroup']
    max_messages_per_chat: int = 500    # client slider default
    cost_cap_usd: float = 5.0           # hard cap (advisory; honored at extract stage)


class ImportHistoryResponse(BaseModel):
    scrape_task_id: str
    scraping_task_id: int       # DB ScrapingTask.id (legacy column name)
    extract_task_id: str
    main_account_id: int


@router.post("/import-history", response_model=ImportHistoryResponse, status_code=202)
def import_chat_history(
    payload: ImportHistoryRequest,
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Trigger a customer-scoped chat-history import → personal KB.

    Flow:
      1. Validate customer has a main account bound (5.0 prereq)
      2. Enqueue scrape_account_groups (Celery) with date / type / max filters
      3. Chain extract_qa_from_messages with customer_id + source_main_account_id

    Returns task IDs the portal can poll for progress.
    """
    if not customer.main_account_id:
        raise HTTPException(
            status_code=400,
            detail="No main account connected. Visit /portal/main-account to scan QR first.",
        )

    # Default to last 30 days if no `since` given
    if not payload.since:
        since_dt = datetime.utcnow() - timedelta(days=30)
        since_iso = since_dt.isoformat()
    else:
        since_iso = payload.since

    # Create a ScrapingTask record for progress tracking
    from app.models.scraping_task import ScrapingTask
    config = {
        "customer_id": customer.id,
        "main_account_id": customer.main_account_id,
        "since": since_iso,
        "until": payload.until,
        "dialog_types": payload.dialog_types,
        "max_messages_per_chat": payload.max_messages_per_chat,
        "cost_cap_usd": payload.cost_cap_usd,
    }
    st = ScrapingTask(
        task_type="customer_kb_import",
        status="pending",
        account_ids_json=json.dumps([customer.main_account_id]),
        # We park the config under result_json's "config" key; live progress is
        # merged in by the Celery task as the same field gets updated.
        result_json=json.dumps({"config": config}, ensure_ascii=False),
    )
    session.add(st); session.commit(); session.refresh(st)

    # Lazy import to break Celery <-> FastAPI startup ordering
    from app.tasks.knowledge_tasks import scrape_account_groups, extract_qa_from_messages

    # Step 1: scrape
    scrape_async = scrape_account_groups.apply_async(
        kwargs=dict(
            account_id=customer.main_account_id,
            scraping_task_id=st.id,
            include_private=True,
            limit_per_chat=payload.max_messages_per_chat,
            since_iso=since_iso,
            until_iso=payload.until,
            dialog_types=payload.dialog_types,
        ),
        queue="low_priority",
    )

    # Step 2: extract — fire-and-forget with a slight delay so scrape has rows to chew on.
    # For larger imports the user should run extract again from the admin tool;
    # MVP: schedule one pass 60s after scrape kicks off.
    extract_async = extract_qa_from_messages.apply_async(
        kwargs=dict(
            customer_id=customer.id,
            source_main_account_id=customer.main_account_id,
            scraping_task_id=st.id,
            window_size=50,
            concurrency=2,
        ),
        countdown=60,
        queue="low_priority",
    )

    return ImportHistoryResponse(
        scrape_task_id=scrape_async.id,
        scraping_task_id=st.id,
        extract_task_id=extract_async.id,
        main_account_id=customer.main_account_id,
    )


@router.get("/import-history/{scraping_task_id}/status")
def import_history_status(
    scraping_task_id: int,
    customer: Customer = Depends(get_active_customer),
    session: Session = Depends(get_session),
) -> Any:
    """Poll progress of an import. Returns DB-side ScrapingTask state + counts."""
    from app.models.scraping_task import ScrapingTask
    st = session.get(ScrapingTask, scraping_task_id)
    if not st:
        raise HTTPException(status_code=404, detail="Task not found")
    # Ownership: account_ids_json contains exactly the customer's main_account_id
    try:
        owner_ids = json.loads(st.account_ids_json or "[]")
    except Exception:
        owner_ids = []
    if customer.main_account_id not in owner_ids:
        raise HTTPException(status_code=404, detail="Task not found")
    progress = {}
    if st.result_json:
        try:
            progress = json.loads(st.result_json)
        except Exception:
            progress = {"raw": st.result_json}

    # Count KB rows already created for this customer (extract may be in flight)
    from sqlmodel import select as _select, func as _func
    kb_count = session.exec(
        _select(_func.count()).select_from(KnowledgeBase)
        .where(KnowledgeBase.customer_id == customer.id)
        .where(KnowledgeBase.source_type == "qa_extracted")
    ).one()

    return {
        "status": st.status,
        "progress": progress,
        "kb_extracted_total": kb_count,
        "error": st.error_message,
        "completed_at": st.completed_at,
    }
