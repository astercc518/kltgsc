"""
admin Group AI Sales endpoints — Phase 2a 仅有 admin 视角。
客户视角的 endpoint (Portal UI) 由 Phase 2b 接。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_current_admin
from app.core.db import get_session
from app.models.user import User
from app.services.case_study_service import (
    create_case_study, delete_case_study,
    list_case_studies, update_case_study,
)
from app.services.customer_icp_service import set_customer_icp_text_and_embed

router = APIRouter(prefix="/admin/group-ai", tags=["admin-group-ai"])


# === Schemas ===

class ICPUpdate(BaseModel):
    icp_text: Optional[str] = None


class ThresholdsUpdate(BaseModel):
    layer2_sim: Optional[float] = None
    layer3_score: Optional[int] = None
    layer3_confidence: Optional[float] = None


class CaseStudyCreate(BaseModel):
    industry: Optional[str] = None
    deal_size: Optional[str] = None
    period: Optional[str] = None
    problem: str
    solution: str
    outcome: str
    tags: list[str] = []


class CaseStudyUpdate(BaseModel):
    industry: Optional[str] = None
    deal_size: Optional[str] = None
    period: Optional[str] = None
    problem: Optional[str] = None
    solution: Optional[str] = None
    outcome: Optional[str] = None
    tags: Optional[list[str]] = None


# === Endpoints ===

@router.put("/customers/{customer_id}/icp")
async def update_customer_icp(
    customer_id: int, body: ICPUpdate,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """设置客户 ICP 画像文本，自动重算 embedding。"""
    ok = await set_customer_icp_text_and_embed(
        session=session, customer_id=customer_id, new_text=body.icp_text,
    )
    if not ok:
        raise HTTPException(404, "customer not found")
    return {"ok": True}


@router.put("/customers/{customer_id}/thresholds")
async def update_customer_thresholds(
    customer_id: int, body: ThresholdsUpdate,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """更新客户 lead detector 三层阈值。"""
    from app.models.customer import Customer
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, "customer not found")
    thresholds = dict(customer.lead_detector_thresholds or {})
    if body.layer2_sim is not None:
        if not 0.0 <= body.layer2_sim <= 1.0:
            raise HTTPException(400, "layer2_sim out of range")
        thresholds["layer2_sim"] = body.layer2_sim
    if body.layer3_score is not None:
        if not 0 <= body.layer3_score <= 100:
            raise HTTPException(400, "layer3_score out of range")
        thresholds["layer3_score"] = body.layer3_score
    if body.layer3_confidence is not None:
        if not 0.0 <= body.layer3_confidence <= 1.0:
            raise HTTPException(400, "layer3_confidence out of range")
        thresholds["layer3_confidence"] = body.layer3_confidence

    customer.lead_detector_thresholds = thresholds
    session.add(customer)
    session.commit()
    return {"ok": True, "thresholds": thresholds}


@router.post("/customers/{customer_id}/case-studies")
async def create_case(
    customer_id: int, body: CaseStudyCreate,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """录入新案例并自动 embed。"""
    case = await create_case_study(
        session=session, customer_id=customer_id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags, source="manual_portal",
    )
    return {"id": case.id}


@router.get("/customers/{customer_id}/case-studies")
async def list_cases(
    customer_id: int, include_inactive: bool = False,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """列举客户案例库。"""
    rows = list_case_studies(
        session=session, customer_id=customer_id, include_inactive=include_inactive,
    )
    return [
        {
            "id": c.id, "industry": c.industry, "deal_size": c.deal_size,
            "period": c.period, "problem": c.problem, "solution": c.solution,
            "outcome": c.outcome, "tags": c.tags, "active": c.active,
            "source": c.source, "created_at": c.created_at,
        }
        for c in rows
    ]


@router.put("/customers/{customer_id}/case-studies/{case_id}")
async def update_case(
    customer_id: int, case_id: int, body: CaseStudyUpdate,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """更新案例字段，改内容时自动重算 embedding。"""
    ok = await update_case_study(
        session=session, case_id=case_id, customer_id=customer_id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


@router.delete("/customers/{customer_id}/case-studies/{case_id}")
async def delete_case(
    customer_id: int, case_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """软删除案例 (active=False)。"""
    ok = delete_case_study(
        session=session, case_id=case_id, customer_id=customer_id,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


from app.models.worker_persona import WorkerPersona
from app.models.chitchat import ChitchatPool
from app.services.case_study_extractor import extract_cases_for_customer


@router.post("/customers/{customer_id}/case-studies/extract")
async def extract_cases_endpoint(
    customer_id: int, max_history: int = 100,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """从主号历史抽取案例候选 (不直接入库, 返回供 admin review)"""
    cases = await extract_cases_for_customer(
        session=session, customer_id=customer_id, max_history=max_history,
    )
    return {"candidates": cases}


class CasesBatchCreate(BaseModel):
    cases: list[CaseStudyCreate]


@router.post("/customers/{customer_id}/case-studies/batch")
async def batch_create_cases(
    customer_id: int, body: CasesBatchCreate,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """admin review 后批量入库 (source='ai_confirmed')"""
    ids = []
    for c in body.cases:
        case = await create_case_study(
            session=session, customer_id=customer_id,
            industry=c.industry, deal_size=c.deal_size, period=c.period,
            problem=c.problem, solution=c.solution, outcome=c.outcome,
            tags=c.tags, source="ai_confirmed",
        )
        ids.append(case.id)
    return {"ids": ids}


# === Worker persona ===

class PersonaUpsert(BaseModel):
    customer_id: int
    display_name: Optional[str] = None
    region: Optional[str] = None
    occupation: Optional[str] = None
    speaking_style: Optional[str] = None
    catchphrases: Optional[list[str]] = None
    active_hours: Optional[dict] = None
    daily_reply_quota: Optional[int] = None
    per_chat_daily_quota: Optional[int] = None
    per_chat_cooldown_minutes: Optional[int] = None
    daily_chitchat_quota: Optional[int] = None
    observation_window_seconds_range: Optional[list[int]] = None
    typing_delay_seconds_range: Optional[list[int]] = None


@router.put("/accounts/{account_id}/persona")
async def upsert_persona(
    account_id: int, body: PersonaUpsert,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """Upsert worker_persona for an account. Creates new row if none exists."""
    existing = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()
    if existing is None:
        existing = WorkerPersona(account_id=account_id, customer_id=body.customer_id)
        session.add(existing)
    # 字段更新 (None 不覆盖)
    for fname in [
        "display_name", "region", "occupation", "speaking_style",
        "catchphrases", "active_hours",
        "daily_reply_quota", "per_chat_daily_quota",
        "per_chat_cooldown_minutes", "daily_chitchat_quota",
        "observation_window_seconds_range", "typing_delay_seconds_range",
    ]:
        val = getattr(body, fname)
        if val is not None:
            setattr(existing, fname, val)
    session.commit()
    session.refresh(existing)
    return {"id": existing.id, "account_id": existing.account_id}


@router.get("/accounts/{account_id}/persona")
async def get_persona_endpoint(
    account_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """Fetch persona row for account. Raises 404 if no row (account uses fallback default)."""
    row = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()
    if row is None:
        raise HTTPException(404, "persona not found, account uses fallback default")
    return {
        "id": row.id, "account_id": row.account_id, "customer_id": row.customer_id,
        "display_name": row.display_name, "region": row.region,
        "occupation": row.occupation, "speaking_style": row.speaking_style,
        "catchphrases": row.catchphrases,
        "active_hours": row.active_hours,
        "daily_reply_quota": row.daily_reply_quota,
        "per_chat_daily_quota": row.per_chat_daily_quota,
        "per_chat_cooldown_minutes": row.per_chat_cooldown_minutes,
        "daily_chitchat_quota": row.daily_chitchat_quota,
        "observation_window_seconds_range": row.observation_window_seconds_range,
        "typing_delay_seconds_range": row.typing_delay_seconds_range,
    }


# === Chitchat pool ===

class ChitchatTopicCreate(BaseModel):
    topic_category: Optional[str] = None
    prompt_template: str
    tags: list[str] = []


@router.post("/customers/{customer_id}/chitchat-topics")
async def create_chitchat_topic(
    customer_id: int, body: ChitchatTopicCreate,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """Create a customer-scoped chitchat pool topic."""
    row = ChitchatPool(
        customer_id=customer_id,
        topic_category=body.topic_category, prompt_template=body.prompt_template,
        tags=body.tags, active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id}


@router.get("/customers/{customer_id}/chitchat-topics")
async def list_chitchat_topics(
    customer_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """List global + customer-scoped active chitchat topics."""
    rows = session.exec(
        select(ChitchatPool).where(
            ((ChitchatPool.customer_id == customer_id) | (ChitchatPool.customer_id.is_(None))),
            ChitchatPool.active == True,
        )
    ).all()
    return [
        {
            "id": r.id, "topic_category": r.topic_category,
            "prompt_template": r.prompt_template, "tags": r.tags,
            "customer_id": r.customer_id,
            "scope": "global" if r.customer_id is None else "customer",
        }
        for r in rows
    ]


@router.delete("/chitchat-topics/{topic_id}")
async def delete_chitchat_topic(
    topic_id: int,
    session: Session = Depends(get_session),
    _admin: User = Depends(get_current_admin),
):
    """Soft delete a chitchat topic (set active=False)."""
    row = session.get(ChitchatPool, topic_id)
    if row is None:
        raise HTTPException(404, "topic not found")
    row.active = False
    session.commit()
    return {"ok": True}
