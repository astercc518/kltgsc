"""
Allocation service — Epic 3.0 MVP.

Provisions a paying customer with:
  • TG accounts picked from the free pool (customer_id IS NULL)
  • AI-customized metadata (username/first_name/bio) matched to industry
  • Source groups picked from the global library by industry tag

All operations are DB-only in Epic 3.0. Epic 3.1 will hook in real Pyrogram
calls to actually set username/bio on Telegram and to join the groups.

Design choices:
  • Idempotent — re-running for the same customer fills up to quota without
    duplicating existing assignments.
  • Atomic per-allocation — each account/group write is its own commit so a
    partial failure leaves the customer with some resources rather than zero.
  • AI customization is best-effort — if the LLM call fails, the account is
    still allocated but customized_* stays NULL (admin can re-run via the
    /reallocate endpoint).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, func, select

from app.models.account import Account
from app.models.customer import Customer
from app.models.source_group import SourceGroup
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


# Industry → AI persona hint (used in the customization prompt)
_INDUSTRY_HINTS = {
    "crypto": "crypto trader / analyst who hangs out in DeFi / NFT / exchange communities",
    "ecommerce": "Shopify seller / DTC brand operator looking for marketing tips",
    "b2b": "B2B export sales rep, often in trade communities, sourcing partners",
    "gaming": "gaming community member / SaaS power user",
    "mcn": "content creator / channel operator running a TG channel matrix",
    "other": "active social user with broad interests",
}

# Per-industry username vibe (lowercase, 8-16 chars, underscore-friendly)
_FALLBACK_USERNAMES = {
    "crypto": ["alpha_trader", "defi_chad", "btc_maxi", "yield_hunter", "onchain_dev",
               "moonbag_pro", "ape_strong", "satoshi_fan"],
    "ecommerce": ["dropship_pro", "shopify_op", "amz_seller", "dtc_growth", "ad_ninja"],
    "b2b": ["export_dan", "trade_anna", "supply_max", "sourcer_lee", "bd_sara"],
    "gaming": ["pwn_master", "raid_lord", "guild_kim", "loot_chaser", "noob_no_more"],
    "mcn": ["yt_curator", "tg_mod", "viral_jay", "creator_ops", "studio_anna"],
    "other": ["nick_smith", "alex_w", "jenny_lee", "mark_t", "lisa_v"],
}


@dataclass
class AccountAllocationResult:
    accounts: List[Account]
    customized: int           # how many got AI metadata
    industry: Optional[str]


@dataclass
class GroupAllocationResult:
    groups: List[SourceGroup]
    industry: Optional[str]
    pool_size: int            # how many candidates existed for the industry


# ──────────────────────────────────────────────────────────────────────────
# Account allocation
# ──────────────────────────────────────────────────────────────────────────

def _count_assigned_accounts(session: Session, customer_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Account)
        .where(Account.customer_id == customer_id)
    ).one()


def _pick_free_accounts(session: Session, n: int) -> List[Account]:
    """Pick N unassigned, healthy accounts from the global pool.

    Exclusions:
      • role='collector' — KB-collection-only accounts (chat-history scraping)
      • role='main' or is_customer_main=True — customer's personal main account
        (Epic 5.0); must never be re-allocated as a worker
    """
    if n <= 0:
        return []
    return session.exec(
        select(Account)
        .where(Account.customer_id.is_(None))
        .where(Account.status.in_(["init", "active"]))
        .where(Account.role != "collector")
        .where(Account.role != "main")
        .where(Account.is_customer_main == False)
        .order_by(Account.health_score.desc(), Account.id)
        .limit(n)
    ).all()


def _customize_account_metadata(
    session: Session, account: Account, industry: Optional[str]
) -> bool:
    """Use LLM to generate industry-matched username / first_name / bio.

    Returns True if customization succeeded, False on fallback.
    """
    industry_key = (industry or "other").lower()
    hint = _INDUSTRY_HINTS.get(industry_key, _INDUSTRY_HINTS["other"])

    prompt = f"""You design realistic Telegram account profiles for B2B lead generation.

Industry: {industry_key}
Target persona: {hint}

Generate a profile that looks like a real person in this space — NOT a sales bot.
Avoid words like 'official', 'support', 'service', 'sales', 'agent', 'bot'.

Output exactly this JSON (no markdown fence):
{{
  "username": "8-16 chars, lowercase letters/digits/underscore only, looks human",
  "first_name": "1-2 words, casual western first name",
  "last_name": "0-2 words, casual surname or empty string",
  "bio": "1 sentence, max 70 chars, sounds like a real practitioner"
}}"""

    try:
        llm = LLMService(session)
        if not llm.is_configured():
            raise RuntimeError("LLM not configured")
        # llm.generate is async; the calling endpoint is a sync def running
        # in FastAPI's threadpool, so a fresh event loop is fine. Wrap in
        # wait_for so a single slow LLM call doesn't blow the whole activation.
        raw = asyncio.run(
            asyncio.wait_for(
                llm.generate(prompt, source="account_customization"),
                timeout=8.0,
            )
        )
        if not raw:
            raise RuntimeError("LLM returned empty response")
        # Strip possible code fence
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").lstrip("json").strip()
        data = json.loads(raw)
        account.customized_username = (data.get("username") or "")[:64] or None
        account.customized_first_name = (data.get("first_name") or "")[:64] or None
        account.customized_last_name = (data.get("last_name") or "")[:64] or None
        account.customized_bio = (data.get("bio") or "")[:280] or None
        return True
    except Exception as e:
        logger.warning(
            "LLM customization failed for account %s (industry=%s): %s — using fallback",
            account.id, industry_key, e,
        )
        # Deterministic fallback so the customer still sees something useful
        username_pool = _FALLBACK_USERNAMES.get(industry_key, _FALLBACK_USERNAMES["other"])
        account.customized_username = random.choice(username_pool) + str(random.randint(10, 99))
        account.customized_first_name = account.customized_username.split("_")[0].capitalize()
        account.customized_bio = f"Interested in {industry_key}."
        return False


def allocate_accounts_for_customer(
    session: Session,
    customer: Customer,
    customize: bool = True,
) -> AccountAllocationResult:
    """Top up the customer's allocated accounts to their account_quota.

    Idempotent: only allocates the delta between current count and quota.
    Returns the newly-allocated accounts (existing ones not included).
    """
    quota = customer.account_quota or 0
    current = _count_assigned_accounts(session, customer.id)
    needed = max(0, quota - current)
    if needed == 0:
        return AccountAllocationResult(accounts=[], customized=0, industry=customer.industry)

    free = _pick_free_accounts(session, needed)
    customized_count = 0
    now = datetime.utcnow()

    for acc in free:
        acc.customer_id = customer.id
        acc.assigned_at = now
        if customize:
            if _customize_account_metadata(session, acc, customer.industry):
                customized_count += 1
        session.add(acc)
        session.commit()
        session.refresh(acc)

    # Sync the denormalized counter on Customer
    customer.account_used = _count_assigned_accounts(session, customer.id)
    customer.updated_at = now
    session.add(customer)
    session.commit()

    return AccountAllocationResult(
        accounts=free,
        customized=customized_count,
        industry=customer.industry,
    )


# ──────────────────────────────────────────────────────────────────────────
# Group allocation
# ──────────────────────────────────────────────────────────────────────────

def _count_assigned_groups(session: Session, customer_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(SourceGroup)
        .where(SourceGroup.customer_id == customer_id)
    ).one()


def _pick_free_groups(
    session: Session, industry: Optional[str], n: int
) -> List[SourceGroup]:
    """Pick N unassigned groups, preferring industry match then fallback."""
    if n <= 0:
        return []
    base = (
        select(SourceGroup)
        .where(SourceGroup.customer_id.is_(None))
        .where(SourceGroup.status == "active")
    )
    if industry:
        # First pass: industry match
        matched = session.exec(
            base.where(SourceGroup.industry == industry).limit(n)
        ).all()
        if len(matched) >= n:
            return matched
        # Second pass: fill remaining with industry-agnostic groups (NULL or 'other')
        remaining = n - len(matched)
        extras = session.exec(
            base.where(
                (SourceGroup.industry.is_(None)) | (SourceGroup.industry == "other")
            ).limit(remaining)
        ).all()
        return list(matched) + list(extras)
    return session.exec(base.limit(n)).all()


def allocate_groups_for_customer(
    session: Session, customer: Customer
) -> GroupAllocationResult:
    """Top up the customer's allocated groups (best-effort)."""
    quota = customer.group_quota or 0
    current = _count_assigned_groups(session, customer.id)
    needed = max(0, quota - current)
    if needed == 0:
        return GroupAllocationResult(groups=[], industry=customer.industry, pool_size=0)

    # Diagnostic: how many candidates exist for this industry?
    pool_q = select(func.count()).select_from(SourceGroup).where(
        SourceGroup.customer_id.is_(None),
        SourceGroup.status == "active",
    )
    if customer.industry:
        pool_q = pool_q.where(
            (SourceGroup.industry == customer.industry)
            | (SourceGroup.industry.is_(None))
            | (SourceGroup.industry == "other")
        )
    pool_size = session.exec(pool_q).one()

    free = _pick_free_groups(session, customer.industry, needed)
    now = datetime.utcnow()
    for g in free:
        g.customer_id = customer.id
        g.assigned_at = now
        session.add(g)
    session.commit()

    customer.group_used = _count_assigned_groups(session, customer.id)
    customer.updated_at = now
    session.add(customer)
    session.commit()

    return GroupAllocationResult(
        groups=free, industry=customer.industry, pool_size=pool_size,
    )


# ──────────────────────────────────────────────────────────────────────────
# Combined entry point — called from billing_service after activation
# ──────────────────────────────────────────────────────────────────────────

def provision_customer(
    session: Session, customer: Customer
) -> tuple[AccountAllocationResult, GroupAllocationResult]:
    """End-to-end provisioning: accounts + groups + industry KB. Used by billing hook.

    Epic 4: KB generation is best-effort — failures here must not block
    account/group allocation. Import is lazy to avoid circular imports.
    """
    logger.info(
        "Provisioning customer %s (plan=%s, industry=%s, "
        "account_quota=%s, group_quota=%s)",
        customer.id, customer.plan, customer.industry,
        customer.account_quota, customer.group_quota,
    )
    accounts = allocate_accounts_for_customer(session, customer)
    groups = allocate_groups_for_customer(session, customer)

    # Epic 4: industry KB
    try:
        from app.services.industry_kb_service import generate_kb_for_customer
        kb_result = generate_kb_for_customer(session, customer)
        logger.info(
            "KB provisioning: created=%d, embedded=%d, skipped=%d",
            len(kb_result.created), kb_result.embedded, kb_result.skipped,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("KB provisioning failed for customer %s: %s", customer.id, e)

    logger.info(
        "Provisioning done: allocated %d accounts (%d customized), "
        "%d groups (industry pool: %d)",
        len(accounts.accounts), accounts.customized,
        len(groups.groups), groups.pool_size,
    )
    return accounts, groups
