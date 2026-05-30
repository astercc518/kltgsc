"""
portal_group_ai — 客户视角端点。

复用 admin 的 service + schema，但 customer_id 从 customer JWT 推断，
不接受 URL 路径参数，避免横向越权。

Endpoints (12 total):
  PUT  /portal/group-ai/icp
  GET  /portal/group-ai/icp
  PUT  /portal/group-ai/thresholds
  GET  /portal/group-ai/case-studies
  POST /portal/group-ai/case-studies
  PUT  /portal/group-ai/case-studies/{case_id}
  DELETE /portal/group-ai/case-studies/{case_id}
  POST /portal/group-ai/case-studies/extract
  POST /portal/group-ai/case-studies/batch
  GET  /portal/group-ai/accounts
  GET  /portal/group-ai/accounts/{account_id}/persona
  PUT  /portal/group-ai/accounts/{account_id}/persona
  GET  /portal/group-ai/chitchat-topics
  POST /portal/group-ai/chitchat-topics
  GET  /portal/group-ai/stats/recent
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps_customer import get_current_customer
from app.core.db import get_session
# 复用 admin router 的 Pydantic schemas
from app.routers.admin_group_ai import (
    ICPUpdate, ThresholdsUpdate,
    CaseStudyCreate, CaseStudyUpdate, CasesBatchCreate,
    PersonaUpsert, ChitchatTopicCreate,
)
from app.services.case_study_service import (
    create_case_study, update_case_study, delete_case_study, list_case_studies,
)
from app.services.customer_icp_service import set_customer_icp_text_and_embed
from app.services.case_study_extractor import extract_cases_for_customer

router = APIRouter(prefix="/portal/group-ai", tags=["portal-group-ai"])


# =============================================================================
# ICP
# =============================================================================

@router.put("/icp")
async def update_my_icp(
    body: ICPUpdate,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """设置自己的 ICP 画像文本，自动重算 embedding。"""
    ok = await set_customer_icp_text_and_embed(
        session=session, customer_id=customer.id, new_text=body.icp_text,
    )
    if not ok:
        raise HTTPException(404, "customer not found (auth ok but DB miss)")
    return {"ok": True}


@router.get("/icp")
async def get_my_icp(
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """返回自己的 ICP 文本 + embedding 状态 + 阈值。"""
    # Re-fetch to get fresh DB state
    from app.models.customer import Customer
    c = session.get(Customer, customer.id)
    return {
        "icp_text": c.icp_profile_text,
        "has_embedding": c.icp_profile_embedding is not None,
        "thresholds": c.lead_detector_thresholds,
    }


# =============================================================================
# Thresholds
# =============================================================================

@router.put("/thresholds")
async def update_my_thresholds(
    body: ThresholdsUpdate,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """更新自己的 lead detector 三层阈值。"""
    from app.models.customer import Customer
    c = session.get(Customer, customer.id)
    thresholds = dict(c.lead_detector_thresholds or {})
    if body.layer2_sim is not None:
        if not 0.0 <= body.layer2_sim <= 1.0:
            raise HTTPException(400, "layer2_sim out of range [0, 1]")
        thresholds["layer2_sim"] = body.layer2_sim
    if body.layer3_score is not None:
        if not 0 <= body.layer3_score <= 100:
            raise HTTPException(400, "layer3_score out of range [0, 100]")
        thresholds["layer3_score"] = body.layer3_score
    if body.layer3_confidence is not None:
        if not 0.0 <= body.layer3_confidence <= 1.0:
            raise HTTPException(400, "layer3_confidence out of range [0, 1]")
        thresholds["layer3_confidence"] = body.layer3_confidence
    c.lead_detector_thresholds = thresholds
    session.add(c)
    session.commit()
    return {"ok": True, "thresholds": thresholds}


# =============================================================================
# Case studies
# =============================================================================

@router.get("/case-studies")
async def list_my_cases(
    include_inactive: bool = False,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """列举自己的案例库。"""
    rows = list_case_studies(
        session=session, customer_id=customer.id, include_inactive=include_inactive,
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


@router.post("/case-studies")
async def create_my_case(
    body: CaseStudyCreate,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """录入新案例并自动 embed。"""
    case = await create_case_study(
        session=session, customer_id=customer.id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags, source="manual_portal",
    )
    return {"id": case.id}


@router.put("/case-studies/{case_id}")
async def update_my_case(
    case_id: int, body: CaseStudyUpdate,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """更新案例字段，改内容时自动重算 embedding。"""
    ok = await update_case_study(
        session=session, case_id=case_id, customer_id=customer.id,
        industry=body.industry, deal_size=body.deal_size, period=body.period,
        problem=body.problem, solution=body.solution, outcome=body.outcome,
        tags=body.tags,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


@router.delete("/case-studies/{case_id}")
async def delete_my_case(
    case_id: int,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """软删除案例 (active=False)。"""
    ok = delete_case_study(
        session=session, case_id=case_id, customer_id=customer.id,
    )
    if not ok:
        raise HTTPException(404, "case not found")
    return {"ok": True}


@router.post("/case-studies/extract")
async def extract_my_cases(
    max_history: int = 100,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """从主号历史抽取案例候选 (不直接入库，返回供客户 review)。"""
    cases = await extract_cases_for_customer(
        session=session, customer_id=customer.id, max_history=max_history,
    )
    return {"candidates": cases}


@router.post("/case-studies/batch")
async def batch_save_my_cases(
    body: CasesBatchCreate,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """review 后批量入库 (source='ai_confirmed')。"""
    ids = []
    for c in body.cases:
        case = await create_case_study(
            session=session, customer_id=customer.id,
            industry=c.industry, deal_size=c.deal_size, period=c.period,
            problem=c.problem, solution=c.solution, outcome=c.outcome,
            tags=c.tags, source="ai_confirmed",
        )
        ids.append(case.id)
    return {"ids": ids}


# =============================================================================
# Worker accounts + persona
# =============================================================================

@router.get("/accounts")
async def list_my_accounts(
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """列出客户名下的 worker 账号 (供 persona 编辑入口)。"""
    from app.models.account import Account
    from sqlmodel import select
    rows = session.exec(
        select(Account).where(
            Account.customer_id == customer.id,
            Account.role == "worker",
        )
    ).all()
    return [{"id": a.id, "phone": a.phone_number, "status": a.status} for a in rows]


@router.get("/accounts/{account_id}/persona")
async def get_my_persona(
    account_id: int,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """获取账号 persona；账号不属于自己 → 404。无 persona 行时返回 None (fallback default)。"""
    from app.models.account import Account
    from app.models.worker_persona import WorkerPersona
    from sqlmodel import select
    acc = session.get(Account, account_id)
    if acc is None or acc.customer_id != customer.id:
        raise HTTPException(404, "account not yours")
    row = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()
    if row is None:
        return None  # fallback default — service 层处理
    return {
        "id": row.id, "account_id": row.account_id,
        "display_name": row.display_name, "region": row.region,
        "occupation": row.occupation, "speaking_style": row.speaking_style,
        "catchphrases": row.catchphrases, "active_hours": row.active_hours,
        "daily_reply_quota": row.daily_reply_quota,
        "per_chat_daily_quota": row.per_chat_daily_quota,
        "per_chat_cooldown_minutes": row.per_chat_cooldown_minutes,
        "daily_chitchat_quota": row.daily_chitchat_quota,
        "observation_window_seconds_range": row.observation_window_seconds_range,
        "typing_delay_seconds_range": row.typing_delay_seconds_range,
    }


@router.put("/accounts/{account_id}/persona")
async def upsert_my_persona(
    account_id: int, body: PersonaUpsert,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """Upsert persona；先验证账号属于本客户，防横向越权。"""
    from app.models.account import Account
    from app.models.worker_persona import WorkerPersona
    from sqlmodel import select
    acc = session.get(Account, account_id)
    if acc is None or acc.customer_id != customer.id:
        raise HTTPException(404, "account not yours")
    existing = session.exec(
        select(WorkerPersona).where(WorkerPersona.account_id == account_id)
    ).first()
    if existing is None:
        existing = WorkerPersona(account_id=account_id, customer_id=customer.id)
        session.add(existing)
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
    return {"ok": True, "id": existing.id}


# =============================================================================
# Chitchat topics
# =============================================================================

@router.get("/chitchat-topics")
async def list_my_chitchat_topics(
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """列出 global + 客户自有的 active chitchat topics。"""
    from app.models.chitchat import ChitchatPool
    from sqlmodel import select
    rows = session.exec(
        select(ChitchatPool).where(
            (ChitchatPool.customer_id == customer.id) | (ChitchatPool.customer_id.is_(None)),
            ChitchatPool.active == True,
        )
    ).all()
    return [
        {
            "id": r.id, "topic_category": r.topic_category,
            "prompt_template": r.prompt_template, "tags": r.tags,
            "scope": "global" if r.customer_id is None else "customer",
        }
        for r in rows
    ]


@router.post("/chitchat-topics")
async def create_my_chitchat_topic(
    body: ChitchatTopicCreate,
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """创建客户自有 chitchat topic。"""
    from app.models.chitchat import ChitchatPool
    row = ChitchatPool(
        customer_id=customer.id,
        topic_category=body.topic_category,
        prompt_template=body.prompt_template,
        tags=body.tags, active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id}


# =============================================================================
# Real-time stats
# =============================================================================

@router.get("/stats/recent")
async def get_my_recent_stats(
    customer=Depends(get_current_customer),
    session: Session = Depends(get_session),
):
    """今日触发 / 发出 / 建议 / 失败 / skip 分布。"""
    from sqlmodel import func, select
    from datetime import datetime, timezone
    from app.models.pending_reply import PendingReply, PendingReplyStatus

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    base = select(func.count(PendingReply.id)).where(
        PendingReply.customer_id == customer.id,
        PendingReply.created_at >= today_start,
    )

    def cnt(*statuses):
        stmt = base.where(PendingReply.status.in_(list(statuses)))
        return int(session.exec(stmt).first() or 0)

    triggered = cnt(*[s.value for s in PendingReplyStatus])
    sent = cnt(PendingReplyStatus.SENT.value)
    suggested = cnt(PendingReplyStatus.SUGGESTED.value)
    failed = cnt(PendingReplyStatus.FAILED.value)
    skipped_human = cnt(PendingReplyStatus.SKIPPED_HUMAN_REPLIED.value)
    skipped_dup = cnt(PendingReplyStatus.SKIPPED_DUP.value)
    skipped_throttled = cnt(PendingReplyStatus.SKIPPED_THROTTLED.value)
    skipped_borderline = cnt(PendingReplyStatus.SKIPPED_BORDERLINE.value)

    return {
        "triggered_today": triggered,
        "sent_today": sent,
        "suggested_today": suggested,
        "failed_today": failed,
        "skipped": {
            "human_replied": skipped_human,
            "dup": skipped_dup,
            "throttled": skipped_throttled,
            "borderline": skipped_borderline,
        },
    }
