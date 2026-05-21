"""
Customer-facing scrape batch orchestration (Epic A).

Responsibilities:
  - preview_cost: estimate cents for a candidate batch (no DB writes)
  - create_batch_draft: persist a ScrapeBatch row + return it
  - start_batch: dispatch the existing scraping_tasks.scrape_members_batch_task
                 with scrape_batch_id injected so the worker can update the
                 customer-facing batch row and charge on completion.

Charging is **deferred to task completion** (per actually-scraped member
count), not at start. We do a pre-flight balance check at start time using
the ceiling estimate (limit_per_group × group_count) so we fail fast if the
customer obviously can't afford the upper bound; if they can't cover the
estimate, the batch refuses to start.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional, Tuple

from sqlmodel import Session

from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.customer import Customer
from app.models.scrape_batch import (
    ScrapeBatch,
    ScrapeCostPreview,
    SCRAPE_CANCELED,
    SCRAPE_FAILED,
    SCRAPE_PENDING,
    SCRAPE_RUNNING,
)
from app.models.scraping_task import ScrapingTask
from app.services import feature_billing
from app.services.wallet_service import get_balance_cents

FEATURE_SLUG = "scrape_group_members"


class ScrapeBatchError(Exception):
    """User-facing error in scrape batch creation/start."""


# ── Pricing ────────────────────────────────────────────────────────────


def _estimate_member_count(limit_per_group: int, group_count: int) -> int:
    return max(limit_per_group, 1) * max(group_count, 0)


def preview_cost(
    session: Session,
    customer_id: int,
    source_links: List[str],
    limit_per_group: int,
) -> ScrapeCostPreview:
    """Estimate ceiling cost without persisting anything."""
    group_count = len([l for l in source_links if l and l.strip()])
    members = _estimate_member_count(limit_per_group, group_count)

    unit = feature_billing.get_unit_price_cents(session, customer_id, FEATURE_SLUG)
    total = unit * members

    balance = get_balance_cents(session, customer_id)
    sufficient = balance >= total
    shortfall = max(total - balance, 0)

    return ScrapeCostPreview(
        estimated_member_count=members,
        unit_price_cents=unit,
        estimated_total_cents=total,
        balance_cents=balance,
        balance_sufficient=sufficient,
        shortfall_cents=shortfall,
    )


# ── Create draft ───────────────────────────────────────────────────────


def create_batch_draft(
    session: Session,
    customer: Customer,
    *,
    name: str,
    source_links: List[str],
    account_ids: Optional[List[int]] = None,
    limit_per_group: int = 200,
    filter_active_only: bool = False,
    filter_has_photo: bool = False,
    filter_has_username: bool = False,
) -> ScrapeBatch:
    """Persist a ScrapeBatch in pending state. Validates inputs only."""
    clean_links = [l.strip() for l in (source_links or []) if l and l.strip()]
    if not clean_links:
        raise ScrapeBatchError("source_links is empty")
    if not name or not name.strip():
        raise ScrapeBatchError("name is required")
    if limit_per_group < 1 or limit_per_group > 10000:
        raise ScrapeBatchError("limit_per_group must be between 1 and 10000")

    # Account ids: if explicitly provided, validate they belong to this customer.
    # If not provided, leave empty — the worker will fall back to customer's pool.
    final_account_ids: List[int] = []
    if account_ids:
        for aid in account_ids:
            acc = session.get(Account, aid)
            if not acc or acc.customer_id != customer.id:
                raise ScrapeBatchError(f"account {aid} not owned by this customer")
            if acc.status != "active":
                raise ScrapeBatchError(f"account {aid} is not active")
            final_account_ids.append(aid)

    unit = feature_billing.get_unit_price_cents(session, customer.id, FEATURE_SLUG)
    est_members = _estimate_member_count(limit_per_group, len(clean_links))
    est_total = unit * est_members

    batch = ScrapeBatch(
        customer_id=customer.id,
        name=name.strip()[:120],
        source_links_json=json.dumps(clean_links),
        account_ids_json=json.dumps(final_account_ids),
        limit_per_group=limit_per_group,
        filter_active_only=filter_active_only,
        filter_has_photo=filter_has_photo,
        filter_has_username=filter_has_username,
        status=SCRAPE_PENDING,
        estimated_unit_price_cents=unit,
        estimated_total_cents=est_total,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


# ── Start ──────────────────────────────────────────────────────────────


def start_batch(session: Session, customer: Customer, batch_id: int) -> ScrapeBatch:
    """Dispatch the Celery scrape task with scrape_batch_id injected.

    Pre-flight checks:
      - feature 已开通
      - 余额 >= estimated_total_cents (ceiling)
      - 状态必须是 pending
    """
    batch = session.get(ScrapeBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise ScrapeBatchError("batch not found")
    if batch.status != SCRAPE_PENDING:
        raise ScrapeBatchError(f"cannot start batch in status '{batch.status}'")

    feature_billing.check_can_afford(
        session, customer.id, FEATURE_SLUG, units=batch.estimated_total_cents // max(batch.estimated_unit_price_cents, 1),
    )

    # Resolve accounts: use specified or fall back to customer's active pool
    account_ids: List[int] = json.loads(batch.account_ids_json or "[]")
    if not account_ids:
        from sqlmodel import select
        rows = session.exec(
            select(Account.id).where(
                Account.customer_id == customer.id,
                Account.status == "active",
            ).limit(20)
        ).all()
        account_ids = list(rows)
    if not account_ids:
        raise ScrapeBatchError("no active TG accounts available for scrape")

    source_links: List[str] = json.loads(batch.source_links_json or "[]")
    filter_config = None
    if batch.filter_active_only or batch.filter_has_photo or batch.filter_has_username:
        filter_config = {
            "active_only": batch.filter_active_only,
            "has_photo": batch.filter_has_photo,
            "has_username": batch.filter_has_username,
        }

    # Create internal ScrapingTask row first so worker has somewhere to log
    task_row = ScrapingTask(
        task_type="scrape_members_batch",
        status="running",
        account_ids_json=json.dumps(account_ids),
        group_links_json=json.dumps(source_links),
    )
    session.add(task_row)
    session.commit()
    session.refresh(task_row)

    celery_task = celery_app.send_task(
        "app.tasks.scraping_tasks.scrape_members_batch_task",
        args=[account_ids, source_links, batch.limit_per_group, task_row.id, filter_config],
        kwargs={"scrape_batch_id": batch.id, "customer_id": customer.id},
    )

    batch.scraping_task_id = task_row.id
    batch.celery_task_id = celery_task.id
    batch.status = SCRAPE_RUNNING
    batch.started_at = datetime.utcnow()
    task_row.celery_task_id = celery_task.id
    session.add_all([batch, task_row])
    session.commit()
    session.refresh(batch)
    return batch


# ── Cancel ─────────────────────────────────────────────────────────────


def cancel_batch(session: Session, customer: Customer, batch_id: int) -> ScrapeBatch:
    """Mark a pending batch as canceled. Running batches can't be canceled
    cleanly via this API (Celery revoke is best-effort and out-of-scope)."""
    batch = session.get(ScrapeBatch, batch_id)
    if not batch or batch.customer_id != customer.id:
        raise ScrapeBatchError("batch not found")
    if batch.status != SCRAPE_PENDING:
        raise ScrapeBatchError(f"cannot cancel batch in status '{batch.status}'")
    batch.status = SCRAPE_CANCELED
    batch.completed_at = datetime.utcnow()
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


# ── Worker callback ────────────────────────────────────────────────────


def finalize_batch_from_worker(
    session: Session,
    batch_id: int,
    scraped_count: int,
    new_users_count: int,
    failed_group_count: int,
    error_message: Optional[str] = None,
) -> None:
    """Called by scrape_members_batch_task on completion.

    Updates progress fields and charges the wallet for the actually-scraped
    member count (not the ceiling estimate). Idempotent via idempotency_key.
    """
    batch = session.get(ScrapeBatch, batch_id)
    if not batch:
        return

    batch.scraped_count = scraped_count
    batch.new_users_count = new_users_count
    batch.failed_group_count = failed_group_count
    batch.completed_at = datetime.utcnow()

    if error_message:
        batch.status = SCRAPE_FAILED
        batch.error_message = error_message[:500]
        session.add(batch)
        session.commit()
        return

    # Charge for actually scraped members (1¢ × N by default)
    if scraped_count > 0:
        try:
            tx = feature_billing.charge(
                session,
                customer_id=batch.customer_id,
                slug=FEATURE_SLUG,
                units=scraped_count,
                idempotency_key=f"scrape-batch:{batch.id}",
                description=f"Scrape batch #{batch.id} — {scraped_count} members",
            )
            batch.charged_cents = abs(tx.amount_cents)
        except Exception as e:
            # If charge fails (insufficient balance edge case, registry issue)
            # we still mark completed but record the error so admin can reconcile.
            batch.status = SCRAPE_FAILED
            batch.error_message = f"scrape ok but charge failed: {e}"[:500]
            session.add(batch)
            session.commit()
            return

    batch.status = "completed"
    session.add(batch)
    session.commit()
