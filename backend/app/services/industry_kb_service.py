"""
Industry KB auto-generation — Epic 4.0 MVP.

For each paying customer, generate a small industry-specific knowledge base
that the AI service layer can RAG-retrieve from. KB entries are tagged with
customer_id so they only surface in that customer's pipeline.

MVP scope (NOT included — Epic 4.1):
  • Real web scraping / RSS / PDF ingestion
  • Customer-uploaded documents
  • KB template editor UI
  • Scheduled re-generation

Current approach:
  4 LLM-generated KB entries per customer covering:
    1. Industry overview
    2. Customer pain points
    3. Sales Q&A
    4. TG opening lines
  Each entry gets a 768-d Vertex embedding for pgvector retrieval.

Failure handling:
  • LLM timeout (8s per topic) — skip that topic, log warning, keep others
  • Embedding failure — KB row still written, embedding stays NULL
    (kb_retrieval falls back to keyword search for those rows)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, func, select

from app.models.customer import Customer
from app.models.knowledge_base import KnowledgeBase
from app.services.embedding_service import EmbeddingService
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


# Per-topic LLM prompt — {industry} is the customer's industry string
_KB_TOPICS = [
    {
        "category": "industry_overview",
        "name_tpl": "[{industry}] Industry Overview",
        "prompt_tpl": (
            "Write a concise overview of the {industry} industry for use by an "
            "AI sales assistant. Cover: market size (2026), key players, common "
            "business models, and 2-3 main trends. ~250 words. Plain text, no "
            "markdown headings."
        ),
    },
    {
        "category": "pain_points",
        "name_tpl": "[{industry}] Customer Pain Points",
        "prompt_tpl": (
            "List 5 specific pain points that {industry} customers face when "
            "looking for solutions. For each pain point, give 1-2 sentences "
            "explaining why it matters and how a partner can help. Format as a "
            "numbered list. ~250 words."
        ),
    },
    {
        "category": "sales_qa",
        "name_tpl": "[{industry}] Sales Q&A",
        "prompt_tpl": (
            "Generate 6 common questions a prospect in the {industry} space "
            "would ask a vendor, plus persuasive but honest answers. Format "
            "strictly as:\n"
            "Q1: ...\nA1: ...\n\nQ2: ...\nA2: ...\n\n... (repeat to Q6/A6). "
            "~400 words total."
        ),
    },
    {
        "category": "opening_lines",
        "name_tpl": "[{industry}] TG Opening Lines",
        "prompt_tpl": (
            "Write 8 natural Telegram DM opening lines for engaging a stranger "
            "in the {industry} space. Each line: < 60 chars, conversational, "
            "curiosity-driven, NOT obvious sales. Number them 1-8. The AI will "
            "pick one per conversation based on the user's context."
        ),
    },
]


@dataclass
class KBGenerationResult:
    industry: Optional[str]
    created: List[KnowledgeBase]
    embedded: int            # how many of `created` got a non-null embedding
    skipped: int             # how many topics the LLM failed to answer


# ── helpers ────────────────────────────────────────────────────────────

def _existing_count(session: Session, customer_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(KnowledgeBase)
        .where(KnowledgeBase.customer_id == customer_id)
    ).one()


def _generate_llm_text(session: Session, prompt: str, timeout: float = 30.0) -> Optional[str]:
    """Sync wrapper around async LLM call with hard timeout.

    KB prompts produce 250-400 word outputs, much longer than account-metadata
    customization — needs ~30s headroom for first-token + streaming.
    """
    try:
        llm = LLMService(session)
        if not llm.is_configured():
            logger.warning("KB LLM: not configured")
            return None
        result = asyncio.run(
            asyncio.wait_for(
                llm.generate(prompt, source="kb_generation"),
                timeout=timeout,
            )
        )
        if not result:
            logger.warning("KB LLM returned None/empty for prompt len=%d", len(prompt))
        return result
    except asyncio.TimeoutError:
        logger.warning("KB LLM timed out after %.1fs", timeout)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("KB LLM generation failed: %r", e)
        return None


def _embed_text(session: Session, text: str, timeout: float = 15.0) -> Optional[List[float]]:
    try:
        es = EmbeddingService(session)
        if not es.is_configured():
            logger.warning("KB embed: not configured")
            return None
        return asyncio.run(
            asyncio.wait_for(
                es.embed(text, source="kb_generation"),
                timeout=timeout,
            )
        )
    except asyncio.TimeoutError:
        logger.warning("KB embedding timed out after %.1fs", timeout)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("KB embedding failed: %r", e)
        return None


# ── public API ────────────────────────────────────────────────────────

def generate_kb_for_customer(
    session: Session,
    customer: Customer,
    skip_if_exists: bool = True,
) -> KBGenerationResult:
    """Generate the 4-topic industry KB for the customer.

    If skip_if_exists=True and the customer already has KB rows, the call is
    a no-op (idempotent — safe to call after every activation/reallocation).
    """
    industry = (customer.industry or "general").lower()

    if skip_if_exists and _existing_count(session, customer.id) > 0:
        logger.info(
            "Customer %s already has KB entries — skipping generation", customer.id,
        )
        return KBGenerationResult(industry=industry, created=[], embedded=0, skipped=0)

    created: List[KnowledgeBase] = []
    embedded = 0
    skipped = 0
    now = datetime.utcnow()

    for topic in _KB_TOPICS:
        name = topic["name_tpl"].format(industry=industry)
        prompt = topic["prompt_tpl"].format(industry=industry)

        text = _generate_llm_text(session, prompt)
        if not text:
            skipped += 1
            continue

        emb = _embed_text(session, text)

        kb = KnowledgeBase(
            name=name,
            description=f"Auto-generated for {industry} customer #{customer.id}",
            content=text.strip(),
            source_type="industry_template",
            category=topic["category"],
            language="en",
            customer_id=customer.id,
            embedding=emb,
        )
        session.add(kb)
        session.commit()
        session.refresh(kb)
        created.append(kb)
        if emb is not None:
            embedded += 1

    logger.info(
        "KB generation for customer %s (industry=%s): created=%d, embedded=%d, skipped=%d",
        customer.id, industry, len(created), embedded, skipped,
    )
    return KBGenerationResult(
        industry=industry, created=created, embedded=embedded, skipped=skipped,
    )


def regenerate_kb_for_customer(
    session: Session, customer: Customer
) -> KBGenerationResult:
    """Force regeneration — delete existing customer KB rows first.

    Use case: customer changed industry, or admin wants a fresh take after
    upgrading prompts.
    """
    rows = session.exec(
        select(KnowledgeBase).where(KnowledgeBase.customer_id == customer.id)
    ).all()
    for r in rows:
        session.delete(r)
    session.commit()
    logger.info("Deleted %d existing KB rows for customer %s", len(rows), customer.id)
    return generate_kb_for_customer(session, customer, skip_if_exists=False)
