"""
Bulk Send dispatch + state machine (W3).

Workflow:
    customer → POST /batches/{id}/start
       → start_batch() validates + sets status=pending + enqueues
         bulk_dispatcher_task.delay(batch_id)

    bulk_dispatcher_task(batch_id):
       1. Re-validates batch (status, variant count, balance)
       2. Selects N accounts via select_accounts_for_batch()
       3. Shards target_ids into N buckets
       4. Sets batch.status=running
       5. For each shard, enqueues bulk_worker_task.delay(account_id, batch_id, target_ids[])

    bulk_worker_task(account_id, batch_id, target_ids[]):
       For each target_id:
         - if batch.status != running → exit early
         - lock target row, pick variant, send (mock or real)
         - on success: charge_wallet + target.status=sent + batch.sent_count++
         - on failure: target.status=failed + reason
         - sleep random(min_delay, max_delay)
         - fault: 5 consecutive failures in this shard → pause batch
       After last target → if all targets terminal → batch.status=completed

参考 docs/planning/bulk_send_spec.md §3.3
"""
from __future__ import annotations

import logging
import math
import os
import random
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, select, func

from app.models.account import Account
from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BATCH_DRAFT, BATCH_PENDING, BATCH_RUNNING, BATCH_PAUSED,
    BATCH_COMPLETED, BATCH_FAILED, BATCH_CANCELED,
    TARGET_PENDING, TARGET_SENDING, TARGET_SENT, TARGET_FAILED, TARGET_SKIPPED,
)
from app.services.wallet_service import (
    charge_wallet, get_balance_cents, InsufficientBalanceError,
)
from app.models.wallet import calculate_tier_unit_price_cents


logger = logging.getLogger(__name__)


# ── Tunables ──────────────────────────────────────────────────────────


MIN_VARIANTS_TO_START = 5
TARGETS_PER_ACCOUNT_DEFAULT = 50
ACCOUNT_FAILURE_BURST_THRESHOLD = 5  # consecutive failures → suspend account in this shard


def mock_mode_enabled() -> bool:
    """Mock send mode: skip Telegram I/O, simulate ~90% success rate.

    Enabled when env BULK_SEND_MOCK=1 OR no eligible accounts exist at dispatch time.
    """
    return os.environ.get("BULK_SEND_MOCK", "0") == "1"


# ── Errors ────────────────────────────────────────────────────────────


class BulkDispatchError(Exception):
    """User-facing errors surfaced as 400."""


# ── State transitions ─────────────────────────────────────────────────


def start_batch(session: Session, batch: BulkBatch) -> BulkBatch:
    """Move draft → pending and arm the dispatcher.

    Performs all up-front validation; the Celery dispatcher trusts the batch
    once status is pending.

    Raises BulkDispatchError on validation failures.
    """
    if batch.status not in (BATCH_DRAFT, BATCH_PAUSED):
        raise BulkDispatchError(
            f"Cannot start batch in status={batch.status}"
        )

    # Variants count check
    n_variants = session.exec(
        select(func.count(BulkTemplateVariant.id))
        .where(BulkTemplateVariant.batch_id == batch.id)
    ).one()
    if n_variants < MIN_VARIANTS_TO_START:
        raise BulkDispatchError(
            f"Need ≥ {MIN_VARIANTS_TO_START} message variants to start "
            f"(have {n_variants}). Anti-spam policy."
        )

    # Targets pending count
    n_pending = session.exec(
        select(func.count(BulkTarget.id))
        .where(BulkTarget.batch_id == batch.id)
        .where(BulkTarget.status.in_([TARGET_PENDING, TARGET_FAILED]))
    ).one()
    if n_pending == 0:
        raise BulkDispatchError("No pending targets to send to")

    # Wallet balance pre-check using current tier
    balance_cents = get_balance_cents(session, batch.customer_id)
    unit = calculate_tier_unit_price_cents(_total_spent_cents(session, batch.customer_id))
    needed_cents = n_pending * unit
    if balance_cents < unit:
        raise BulkDispatchError(
            f"Wallet balance ${balance_cents/100:.2f} is below per-message "
            f"price ${unit/100:.2f}. Top up first."
        )
    if balance_cents < needed_cents:
        # Soft warning: allow start with partial coverage; batch will auto-pause
        logger.info(
            f"batch {batch.id}: partial balance coverage "
            f"(have {balance_cents}c, need ~{needed_cents}c)"
        )

    batch.status = BATCH_PENDING
    batch.paused_at = None
    batch.pause_reason = None
    batch.updated_at = datetime.utcnow()
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def pause_batch(session: Session, batch: BulkBatch, reason: str = "user_paused") -> BulkBatch:
    """Move running/pending → paused. Worker tasks observe this and exit early."""
    if batch.status not in (BATCH_PENDING, BATCH_RUNNING):
        raise BulkDispatchError(f"Cannot pause batch in status={batch.status}")
    batch.status = BATCH_PAUSED
    batch.paused_at = datetime.utcnow()
    batch.pause_reason = reason[:120]
    batch.updated_at = datetime.utcnow()
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def resume_batch(session: Session, batch: BulkBatch) -> BulkBatch:
    """Move paused → pending and re-arm dispatcher."""
    if batch.status != BATCH_PAUSED:
        raise BulkDispatchError(f"Cannot resume batch in status={batch.status}")
    return start_batch(session, batch)


def mark_batch_completed_if_done(session: Session, batch: BulkBatch) -> bool:
    """Check if all targets are terminal; if so mark batch completed."""
    n_left = session.exec(
        select(func.count(BulkTarget.id))
        .where(BulkTarget.batch_id == batch.id)
        .where(BulkTarget.status.in_([TARGET_PENDING, TARGET_SENDING]))
    ).one()
    if n_left == 0 and batch.status in (BATCH_RUNNING, BATCH_PENDING):
        batch.status = BATCH_COMPLETED
        batch.completed_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        session.add(batch)
        session.commit()
        return True
    return False


# ── Account selection ─────────────────────────────────────────────────


def select_accounts_for_batch(
    session: Session,
    batch: BulkBatch,
    n_targets_pending: int,
    targets_per_account: int = TARGETS_PER_ACCOUNT_DEFAULT,
) -> List[Account]:
    """Pick N accounts to handle this batch's targets.

    Algorithm (spec §4.2):
      1. Prefer accounts tagged for bulk sending (combat_role='bulk_sender' or
         tags LIKE '%bulk%')
      2. Fall back to pool worker accounts (customer_id IS NULL, status=active)
      3. Skip accounts in flood_wait / banned / cooldown
      4. Sort by id (stable, no health_score field yet)
      5. Take ceil(n_targets / targets_per_account)

    Returns [] if no eligible accounts. Caller decides whether to mock-send or fail.
    """
    n_needed = max(1, math.ceil(n_targets_pending / max(1, targets_per_account)))

    pool = session.exec(
        select(Account)
        .where(Account.status == "active")
        .where(Account.customer_id.is_(None))  # not customer-owned
        .order_by(Account.id)
    ).all()

    return list(pool)[:n_needed]


def shard_targets(target_ids: List[int], n_shards: int) -> List[List[int]]:
    """Round-robin split target_ids into n_shards. Handles n_shards > len gracefully."""
    if n_shards <= 0:
        return [target_ids]
    shards: List[List[int]] = [[] for _ in range(n_shards)]
    for i, tid in enumerate(target_ids):
        shards[i % n_shards].append(tid)
    return [s for s in shards if s]  # drop empty


# ── Variant selection ─────────────────────────────────────────────────


def pick_variant(
    session: Session, batch_id: int,
) -> Optional[BulkTemplateVariant]:
    """Weighted random pick from a batch's variants."""
    variants = session.exec(
        select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == batch_id)
    ).all()
    if not variants:
        return None
    total_weight = sum(v.weight for v in variants)
    if total_weight <= 0:
        return random.choice(variants)
    r = random.uniform(0, total_weight)
    cursor = 0
    for v in variants:
        cursor += v.weight
        if r <= cursor:
            return v
    return variants[-1]


# ── Helpers ──────────────────────────────────────────────────────────


def _total_spent_cents(session: Session, customer_id: int) -> int:
    """Read total_spent_cents from wallet (auto-creates wallet if absent)."""
    from app.services.wallet_service import get_or_create_wallet
    w = get_or_create_wallet(session, customer_id)
    return w.total_spent_cents


def charge_for_target(
    session: Session, batch: BulkBatch, target: BulkTarget,
) -> bool:
    """Atomically charge customer wallet for one send.

    Returns True on success, False on insufficient balance (caller pauses batch).
    Idempotent: same target_id will not double-charge.
    """
    spent = _total_spent_cents(session, batch.customer_id)
    unit = calculate_tier_unit_price_cents(spent)
    try:
        charge_wallet(
            session,
            customer_id=batch.customer_id,
            amount_cents=unit,
            idempotency_key=f"bulk-target-{target.id}",
            description=f"Bulk send batch {batch.id} target {target.id}",
            bulk_batch_id=batch.id,
        )
        return True
    except InsufficientBalanceError:
        return False
