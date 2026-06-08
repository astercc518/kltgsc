"""
Bulk Send Celery tasks (W3).

- bulk_dispatcher_task: arms the worker fan-out for one batch
- bulk_worker_task: per-account shard processing loop with wallet charging

Both tasks are short-circuit safe: if batch.status drifts (paused/canceled),
they exit early without touching wallet.

参考 docs/planning/bulk_send_spec.md §3.3
"""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import List

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.account import Account
from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BATCH_PENDING, BATCH_RUNNING, BATCH_PAUSED, BATCH_COMPLETED, BATCH_FAILED,
    TARGET_PENDING, TARGET_SENDING, TARGET_SENT, TARGET_FAILED,
)
from app.services.bulk_dispatch_service import (
    select_accounts_for_batch, shard_targets, pick_variant,
    charge_for_target, mark_batch_completed_if_done,
    mock_mode_enabled, ACCOUNT_FAILURE_BURST_THRESHOLD,
)


logger = logging.getLogger(__name__)


# ── Dispatcher ────────────────────────────────────────────────────────


@celery_app.task(bind=True, soft_time_limit=600, time_limit=900)
def bulk_dispatcher_task(self, batch_id: int) -> dict:
    """Fan out worker tasks for one batch.

    Idempotent: re-running while status=running is a no-op (no new shards).
    """
    with Session(engine) as s:
        batch = s.get(BulkBatch, batch_id)
        if not batch:
            return {"error": f"batch {batch_id} not found"}
        if batch.status not in (BATCH_PENDING, BATCH_RUNNING):
            logger.info(f"batch {batch_id} not pending/running (status={batch.status}); skip")
            return {"skipped": True, "status": batch.status}

        # Resume-friendly: pick up any target left as pending or previously failed
        pending_targets = s.exec(
            select(BulkTarget.id)
            .where(BulkTarget.batch_id == batch_id)
            .where(BulkTarget.status.in_([TARGET_PENDING, TARGET_FAILED]))
            .order_by(BulkTarget.id)
        ).all()

        if not pending_targets:
            mark_batch_completed_if_done(s, batch)
            return {"completed": True}

        accounts = select_accounts_for_batch(s, batch, len(pending_targets))

        if not accounts:
            if not mock_mode_enabled():
                logger.warning(f"batch {batch_id}: no eligible accounts; pausing")
                batch.status = BATCH_PAUSED
                batch.paused_at = datetime.utcnow()
                batch.pause_reason = "no_eligible_accounts"
                s.add(batch)
                s.commit()
                return {"paused": True, "reason": "no_eligible_accounts"}
            # mock mode: synthesize one fake account_id=0 to drive the worker
            account_ids = [0]
        else:
            account_ids = [a.id for a in accounts]

        shards = shard_targets(pending_targets, len(account_ids))

        batch.status = BATCH_RUNNING
        if not batch.started_at:
            batch.started_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        s.add(batch)
        s.commit()

        for account_id, shard in zip(account_ids, shards):
            bulk_worker_task.delay(account_id, batch_id, shard)

        return {
            "batch_id": batch_id,
            "accounts": len(account_ids),
            "targets": len(pending_targets),
            "shards": [len(s) for s in shards],
            "mock_mode": mock_mode_enabled() or not accounts,
        }


# ── Worker ───────────────────────────────────────────────────────────


@celery_app.task(bind=True, soft_time_limit=7200, time_limit=10800)
def bulk_worker_task(self, account_id: int, batch_id: int, target_ids: List[int]) -> dict:
    """Process one shard of targets for one account.

    Single-threaded loop. Sleeps random(min,max) between sends to spread load.
    Re-reads batch.status each iteration so pause/cancel takes effect quickly.
    """
    consecutive_failures = 0
    processed = 0
    succeeded = 0
    failed = 0
    insufficient_balance = False

    # Read once outside the per-target loop; these never change mid-batch.
    with Session(engine) as s:
        batch = s.get(BulkBatch, batch_id)
        if not batch:
            return {"error": "batch vanished"}
        min_delay = batch.min_delay_sec
        max_delay = batch.max_delay_sec

    for tid in target_ids:
        with Session(engine) as s:
            # Re-fetch batch — status may have flipped to paused
            batch = s.get(BulkBatch, batch_id)
            if not batch:
                return {"error": "batch vanished"}
            if batch.status != BATCH_RUNNING:
                logger.info(f"worker {account_id}/{batch_id}: batch status={batch.status}; stop")
                break

            # Lock target row
            target = s.exec(
                select(BulkTarget).where(BulkTarget.id == tid).with_for_update()
            ).first()
            if not target:
                continue
            if target.status != TARGET_PENDING and target.status != TARGET_FAILED:
                # Already done by some other shard / retry
                continue

            target.status = TARGET_SENDING
            target.assigned_account_id = account_id if account_id else None
            s.add(target)
            s.commit()

            # Pick variant
            variant = pick_variant(s, batch_id)
            if variant is None:
                target.status = TARGET_FAILED
                target.failed_reason = "no_variants"
                s.add(target)
                s.commit()
                failed += 1
                continue

            # Send (real or mock)
            send_ok, send_err = _do_send(
                s, account_id, target, variant, mock=mock_mode_enabled() or account_id == 0,
            )

            if send_ok:
                # Charge wallet first (atomic); if balance gone, pause batch
                charged = charge_for_target(s, batch, target)
                if not charged:
                    insufficient_balance = True
                    target.status = TARGET_PENDING  # roll back: didn't actually charge
                    s.add(target)
                    s.commit()
                    break

                target.status = TARGET_SENT
                target.sent_at = datetime.utcnow()
                target.failed_reason = None
                target.variant_id = variant.id
                s.add(target)

                variant.use_count += 1
                s.add(variant)

                batch.sent_count = (batch.sent_count or 0) + 1
                batch.updated_at = datetime.utcnow()
                s.add(batch)

                s.commit()
                succeeded += 1
                consecutive_failures = 0
            else:
                target.status = TARGET_FAILED
                target.failed_reason = (send_err or "send_failed")[:200]
                s.add(target)

                batch.failed_count = (batch.failed_count or 0) + 1
                batch.updated_at = datetime.utcnow()
                s.add(batch)

                s.commit()
                failed += 1
                consecutive_failures += 1

            processed += 1

        # Failure burst → pause batch (account suspect)
        if consecutive_failures >= ACCOUNT_FAILURE_BURST_THRESHOLD:
            with Session(engine) as s:
                batch = s.get(BulkBatch, batch_id)
                if batch and batch.status == BATCH_RUNNING:
                    batch.status = BATCH_PAUSED
                    batch.paused_at = datetime.utcnow()
                    batch.pause_reason = f"account_{account_id}_failure_burst"
                    batch.updated_at = datetime.utcnow()
                    s.add(batch)
                    s.commit()
            logger.warning(
                f"worker {account_id}/{batch_id}: paused after "
                f"{consecutive_failures} consecutive failures"
            )
            break

        # Sleep between sends (with anti-spam jitter)
        delay = random.uniform(min_delay, max_delay)
        time.sleep(max(0.1, delay if not mock_mode_enabled() else min(1.0, delay)))

    # Insufficient balance → pause batch
    if insufficient_balance:
        with Session(engine) as s:
            batch = s.get(BulkBatch, batch_id)
            if batch and batch.status == BATCH_RUNNING:
                batch.status = BATCH_PAUSED
                batch.paused_at = datetime.utcnow()
                batch.pause_reason = "insufficient_balance"
                batch.updated_at = datetime.utcnow()
                s.add(batch)
                s.commit()

    # If this was the last shard to finish, mark batch completed
    with Session(engine) as s:
        batch = s.get(BulkBatch, batch_id)
        if batch:
            mark_batch_completed_if_done(s, batch)

    return {
        "account_id": account_id,
        "batch_id": batch_id,
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "stopped_for_balance": insufficient_balance,
    }


# ── Send primitive ────────────────────────────────────────────────────


def _do_send(
    session: Session,
    account_id: int,
    target: BulkTarget,
    variant: BulkTemplateVariant,
    mock: bool,
) -> tuple[bool, str | None]:
    """Send a single message. Returns (success, error_string_or_None).

    Resolves the target by username > phone > user_id priority via the peer
    resolution layer. A ``perm:``-prefixed error string denotes a target-level
    permanent failure (e.g. unknown username, privacy restriction) — the caller
    should mark the target permanently failed rather than retrying. Real sending
    is enabled by setting BULK_SEND_MOCK=0 once the account pool is ready.
    """
    if mock:
        # 90% success simulation, no I/O
        ok = random.random() < 0.9
        return ok, None if ok else "mock_failure"

    # Real send: 解析层按 username > phone > user_id 优先级发送
    if not (target.tg_user_id or target.tg_username or target.phone):
        return False, "no_handle"

    account = session.get(Account, account_id)
    if not account:
        return False, "account_missing"

    try:
        import asyncio
        from app.services.telegram_client import resolve_and_send_with_client
        ok, err = asyncio.run(
            resolve_and_send_with_client(
                account,
                tg_user_id=target.tg_user_id,
                tg_username=target.tg_username,
                phone=target.phone,
                message=variant.content,
                db_session=session,
            )
        )
        return bool(ok), (None if ok else err)
    except Exception as e:  # broad — Pyrogram raises many exception types
        return False, str(e)[:200]
