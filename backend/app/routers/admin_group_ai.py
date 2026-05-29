"""
admin Group AI Sales endpoints — Phase 2a 仅有 admin 视角。
客户视角的 endpoint (Portal UI) 由 Phase 2b 接。

TODO Phase 2b: 替换成现有 admin 权限依赖:
    from app.api.deps import get_current_admin
    并在每个 endpoint 加 _admin: User = Depends(get_current_admin)
    参考 app/api/v1/endpoints/admin_billing.py 的模式。

当前 Phase 2a 不加 auth (staging 灰度时手动加)。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
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
    customer_id: int, body: ICPUpdate, session: Session = Depends(get_session),
):
    """设置客户 ICP 画像文本，自动重算 embedding。"""
    ok = set_customer_icp_text_and_embed(
        session=session, customer_id=customer_id, new_text=body.icp_text,
    )
    if not ok:
        raise HTTPException(404, "customer not found")
    return {"ok": True}


@router.put("/customers/{customer_id}/thresholds")
async def update_customer_thresholds(
    customer_id: int, body: ThresholdsUpdate,
    session: Session = Depends(get_session),
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
):
    """录入新案例并自动 embed。"""
    case = create_case_study(
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
):
    """更新案例字段，改内容时自动重算 embedding。"""
    ok = update_case_study(
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
):
    """软删除案例 (active=False)。"""
    ok = delete_case_study(
        session=session, case_id=case_id, customer_id=customer_id,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


from app.services.case_study_extractor import extract_cases_for_customer


@router.post("/customers/{customer_id}/case-studies/extract")
async def extract_cases_endpoint(
    customer_id: int, max_history: int = 100,
    session: Session = Depends(get_session),
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
):
    """admin review 后批量入库 (source='ai_confirmed')"""
    ids = []
    for c in body.cases:
        case = create_case_study(
            session=session, customer_id=customer_id,
            industry=c.industry, deal_size=c.deal_size, period=c.period,
            problem=c.problem, solution=c.solution, outcome=c.outcome,
            tags=c.tags, source="ai_confirmed",
        )
        ids.append(case.id)
    return {"ids": ids}
