"""
知识库召回服务（RAG）

v2：基于 pgvector 的向量召回（cosine distance），失败时回退到原 v1 关键词 ILIKE 路径。

调用方（如 [ai_reply_service.py](app/services/ai_reply_service.py)）使用相同的 retrieve_relevant_kb，但需 await。
format_kb_for_prompt 保持不变，便于复用。
"""
import re
import logging
from typing import List, Optional
from sqlmodel import Session, select, or_
from sqlalchemy import text as sa_text

from app.models.knowledge_base import KnowledgeBase
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


# ── 关键词回退路径用的中文停用词 ──
_STOP = {
    "的", "了", "在", "是", "我", "你", "他", "她", "我们", "你们", "他们",
    "和", "与", "或", "也", "都", "就", "还", "又", "再", "只", "但",
    "什么", "怎么", "哪里", "哪个", "为什么", "如何", "可以", "不能",
    "请问", "请", "谢谢", "好的", "嗯", "啊", "呢", "吗", "吧",
    "this", "that", "the", "is", "are", "and", "or", "to", "of", "in",
}


def _extract_keywords(query: str, max_kw: int = 8) -> List[str]:
    q = query.strip()
    if not q:
        return []

    ascii_words = re.findall(r"[A-Za-z0-9]+", q)
    ascii_words = [w.lower() for w in ascii_words if len(w) >= 2 and w.lower() not in _STOP]

    cn_chars = re.findall(r"[一-鿿]+", q)
    cn_grams = []
    for run in cn_chars:
        if len(run) >= 2:
            for i in range(len(run) - 1):
                g = run[i:i + 2]
                if g not in _STOP:
                    cn_grams.append(g)

    seen = set()
    out = []
    for w in ascii_words + cn_grams:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= max_kw:
            break
    return out


async def retrieve_relevant_kb(
    session: Session,
    query: str,
    top_k: int = 5,
    chat_id_filter: Optional[int] = None,
    topic_filter: Optional[str] = None,
    source_type: Optional[str] = None,
    category_filter: Optional[str] = None,
    similarity_threshold: float = 0.45,
) -> List[KnowledgeBase]:
    """
    向量召回（pgvector cosine distance）。失败回退到关键词 ILIKE。

    Args:
        source_type: 限定来源类型；None = 不限（manual + qa_extracted + file_import 全找）
        similarity_threshold: 相似度阈值，1 - cosine_distance < threshold 的丢弃
    """
    if not query or not query.strip():
        return []

    # —— 1. 向量召回 ——
    try:
        emb_service = EmbeddingService(session)
        if emb_service.is_configured():
            qvec = await emb_service.embed(query)
            if qvec:
                return _vector_search(
                    session, qvec, top_k,
                    chat_id_filter, topic_filter, source_type, category_filter,
                    similarity_threshold,
                )
            else:
                logger.warning("Failed to embed query; falling back to keyword search")
        else:
            logger.info("Embedding service not configured; using keyword search")
    except Exception as e:
        logger.error(f"Vector retrieval error, falling back: {e}")

    # —— 2. 回退：关键词 ILIKE ——
    return _keyword_search(
        session, query, top_k,
        chat_id_filter, topic_filter, source_type, category_filter,
    )


def _vector_search(
    session: Session,
    qvec: List[float],
    top_k: int,
    chat_id_filter: Optional[int],
    topic_filter: Optional[str],
    source_type: Optional[str],
    category_filter: Optional[str],
    similarity_threshold: float,
) -> List[KnowledgeBase]:
    where_clauses = ["embedding IS NOT NULL"]
    params: dict = {"qvec": str(qvec), "top_k": top_k * 2}

    if source_type:
        where_clauses.append("source_type = :source_type")
        params["source_type"] = source_type
    if chat_id_filter is not None:
        where_clauses.append("source_chat_id = :chat_id")
        params["chat_id"] = chat_id_filter
    if topic_filter:
        where_clauses.append("qa_topic = :topic")
        params["topic"] = topic_filter
    if category_filter:
        where_clauses.append("category = :category")
        params["category"] = category_filter

    where_sql = " AND ".join(where_clauses)
    sql = sa_text(
        f"""
        SELECT id, (embedding <=> CAST(:qvec AS vector)) AS distance
        FROM ai_knowledge_base
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :top_k
        """
    )

    rows = session.execute(sql, params).fetchall()
    if not rows:
        return []

    # 阈值过滤：cosine distance 越小越相似（0=完全相同，2=正交反向）
    # 相似度 = 1 - distance；保留 similarity >= threshold 的
    keep_ids = [r[0] for r in rows if (1 - float(r[1])) >= similarity_threshold]
    if not keep_ids:
        # 阈值过严时至少返回 top 1，避免完全空召回
        keep_ids = [rows[0][0]]

    keep_ids = keep_ids[:top_k]
    kbs = session.exec(
        select(KnowledgeBase).where(KnowledgeBase.id.in_(keep_ids))
    ).all()

    # 按原排序复原
    id_order = {kid: i for i, kid in enumerate(keep_ids)}
    return sorted(kbs, key=lambda kb: id_order.get(kb.id, 999))


def _keyword_search(
    session: Session,
    query: str,
    top_k: int,
    chat_id_filter: Optional[int],
    topic_filter: Optional[str],
    source_type: Optional[str],
    category_filter: Optional[str],
) -> List[KnowledgeBase]:
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    stmt = select(KnowledgeBase)
    if source_type:
        stmt = stmt.where(KnowledgeBase.source_type == source_type)
    if chat_id_filter is not None:
        stmt = stmt.where(KnowledgeBase.source_chat_id == chat_id_filter)
    if topic_filter:
        stmt = stmt.where(KnowledgeBase.qa_topic == topic_filter)
    if category_filter:
        stmt = stmt.where(KnowledgeBase.category == category_filter)

    or_clauses = []
    for kw in keywords:
        like = f"%{kw}%"
        or_clauses.append(KnowledgeBase.content.ilike(like))
        or_clauses.append(KnowledgeBase.qa_question.ilike(like))
        or_clauses.append(KnowledgeBase.qa_answer.ilike(like))
    stmt = stmt.where(or_(*or_clauses)).limit(top_k * 8)

    candidates = session.exec(stmt).all()
    if not candidates:
        return []

    def score(kb: KnowledgeBase) -> int:
        s = 0
        q_text = (kb.qa_question or "").lower()
        a_text = (kb.qa_answer or "").lower()
        t_text = (kb.qa_topic or "").lower()
        tag_text = (kb.qa_tags or "").lower()
        c_text = (kb.content or "").lower()
        for kw in keywords:
            kwl = kw.lower()
            s += q_text.count(kwl) * 3
            s += a_text.count(kwl)
            s += t_text.count(kwl) * 2
            s += tag_text.count(kwl)
            s += c_text.count(kwl)
        return s

    candidates.sort(key=score, reverse=True)
    return candidates[:top_k]


def format_kb_for_prompt(items: List[KnowledgeBase], max_chars: int = 1500) -> str:
    """把召回的 KB 拼成可注入 prompt 的字符串。优先 QA 形式，回退到 content 摘要。"""
    if not items:
        return ""
    lines = []
    total = 0
    for kb in items:
        q = (kb.qa_question or "").strip()
        a = (kb.qa_answer or "").strip()
        if q and a:
            chunk = f"- Q：{q}\n  A：{a}"
        else:
            # 文档导入 / 手填 KB：用 content 摘要
            body = (kb.content or "").strip()
            if not body:
                continue
            title = (kb.name or "").strip()
            snippet = body[:400]
            chunk = f"- 【{title}】{snippet}" if title else f"- {snippet}"
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)
    return "\n".join(lines)
