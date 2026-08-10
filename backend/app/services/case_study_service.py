"""
case_study_service — CaseStudy CRUD + 按 solution_topic 查 top-k。

录入 / 更新时自动重算 embedding (problem + solution + outcome 拼接)。
查询走 pgvector cosine 距离 (raw SQL <=> 操作符)。

NOTE: pgvector.sqlalchemy.Vector.cosine_distance() ORM 方法在当前版本不可用
(Comparator 无 cosine_distance attr)。使用 raw SQL fallback:
  ORDER BY embedding <=> CAST(:vec AS vector)
与 kb_retrieval.py 的实现保持一致。
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from sqlmodel import select

from app.models.case_study import CaseStudy
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)


def _build_embed_payload(problem: str, solution: str, outcome: str) -> str:
    parts = [p.strip() for p in [problem, solution, outcome] if p and p.strip()]
    return " | ".join(parts)


async def create_case_study(
    *, session, customer_id: int, industry: Optional[str],
    deal_size: Optional[str], period: Optional[str],
    problem: str, solution: str, outcome: str,
    tags: Optional[list] = None, source: str = "manual_portal",
) -> CaseStudy:
    """
    录入案例并自动生成 embedding。embedding 失败不阻塞写入。

    Returns:
        CaseStudy instance (已 commit + refresh)
    """
    payload = _build_embed_payload(problem, solution, outcome)
    vec = await embed_text(session=session, text=payload)
    if vec is None:
        logger.warning(
            "create_case_study: embedding failed for customer %d, case saved without embedding",
            customer_id,
        )

    case = CaseStudy(
        customer_id=customer_id,
        industry=industry,
        deal_size=deal_size,
        period=period,
        problem=problem,
        solution=solution,
        outcome=outcome,
        tags=tags or [],
        embedding=vec,
        source=source,
        active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


async def update_case_study(
    *, session, case_id: int, customer_id: int,
    industry: Optional[str] = None, deal_size: Optional[str] = None,
    period: Optional[str] = None,
    problem: Optional[str] = None, solution: Optional[str] = None,
    outcome: Optional[str] = None, tags: Optional[list] = None,
) -> bool:
    """
    更新案例字段，改 problem/solution/outcome 时重算 embedding。

    Returns:
        True 成功; False 案例不存在或不属于该 customer
    """
    case = session.get(CaseStudy, case_id)
    if case is None or case.customer_id != customer_id:
        return False

    content_changed = False
    for fname, val in [
        ("industry", industry), ("deal_size", deal_size), ("period", period),
        ("problem", problem), ("solution", solution), ("outcome", outcome),
    ]:
        if val is not None and getattr(case, fname) != val:
            setattr(case, fname, val)
            if fname in ("problem", "solution", "outcome"):
                content_changed = True
    if tags is not None:
        case.tags = tags

    if content_changed:
        payload = _build_embed_payload(case.problem or "", case.solution or "", case.outcome or "")
        case.embedding = await embed_text(session=session, text=payload)

    session.add(case)
    session.commit()
    return True


def delete_case_study(*, session, case_id: int, customer_id: int) -> bool:
    """
    软删除: active=False (保留数据供训练)。

    Returns:
        True 成功; False 案例不存在或不属于该 customer
    """
    case = session.get(CaseStudy, case_id)
    if case is None or case.customer_id != customer_id:
        return False
    case.active = False
    session.add(case)
    session.commit()
    return True


def list_case_studies(
    *, session, customer_id: int, include_inactive: bool = False,
) -> list:
    """
    按 customer_id 列举案例, 默认只返回 active=True, 按 created_at desc 排序。
    """
    stmt = select(CaseStudy).where(CaseStudy.customer_id == customer_id)
    if not include_inactive:
        stmt = stmt.where(CaseStudy.active == True)  # noqa: E712
    stmt = stmt.order_by(CaseStudy.created_at.desc())
    return list(session.exec(stmt).all())


# pgvector cosine threshold: 候选案例与 topic 的最小相似度
MIN_CASE_MATCH_SIMILARITY = 0.4
# pgvector cosine distance = 1 - similarity; threshold <= this value means similarity >= 0.4
MAX_COSINE_DISTANCE = 1.0 - MIN_CASE_MATCH_SIMILARITY


async def find_top_k_for_topic(
    *, session, customer_id: int, topic: str, k: int = 2,
) -> list:
    """
    按 layer3.suggested_solution_topic 找 top-k 相关案例。

    使用 pgvector 余弦距离 (embedding <=> :vec) raw SQL。
    仅返回 cosine distance <= MAX_COSINE_DISTANCE (即 similarity >= 0.4) 的案例。
    embedding 失败时降级到按 last_used_at desc 取 k 条。

    NOTE: CaseStudy.embedding.cosine_distance() ORM 方法不可用（pgvector
    当前版本 Comparator 无 cosine_distance），使用 raw SQL 与 kb_retrieval.py 一致。
    """
    if not topic or not topic.strip():
        return []

    topic_vec = await embed_text(session=session, text=topic)
    if topic_vec is None:
        logger.warning(
            "find_top_k_for_topic: embedding failed, falling back to recency order"
        )
        # 降级: 取最近用过的 k 条
        stmt = (
            select(CaseStudy)
            .where(
                CaseStudy.customer_id == customer_id,
                CaseStudy.active == True,  # noqa: E712
            )
            .order_by(
                CaseStudy.last_used_at.desc().nullslast(),
                CaseStudy.created_at.desc(),
            )
            .limit(k)
        )
        return list(session.exec(stmt).all())

    # pgvector cosine: 距离 (1 - similarity), 越小越相似
    # 与 kb_retrieval.py 使用相同的 raw SQL 模式
    # 同时过滤 distance <= MAX_COSINE_DISTANCE (= 1 - MIN_CASE_MATCH_SIMILARITY)
    # 防止不相关案例注入回复
    stmt = (
        select(CaseStudy)
        .where(
            CaseStudy.customer_id == customer_id,
            CaseStudy.active == True,  # noqa: E712
            CaseStudy.embedding.isnot(None),
            sa.text("embedding <=> CAST(:topic_vec AS vector) <= :max_dist"),
        )
        .order_by(
            sa.text("embedding <=> CAST(:topic_vec AS vector)")
        )
        .limit(k)
    )
    rows = list(
        session.exec(
            stmt.params(topic_vec=str(topic_vec), max_dist=MAX_COSINE_DISTANCE)
        ).all()
    )
    return rows
