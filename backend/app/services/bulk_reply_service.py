"""
Bulk Send W4 — inbound-reply handling.

Detect when a private DM lands on one of our worker accounts that originated
from a previous bulk send, then:
    1. Mark bulk_target.status = 'replied' (idempotent)
    2. Increment bulk_batch.replied_count
    3. Upsert a Lead row with source='bulk' + bulk_batch_id so the existing
       Inbox / CRM / AI co-pilot pipeline picks it up for free.
    4. Broadcast a `bulk_reply` WebSocket event for live portal updates.

Reuse-first: leads created here flow through the same handover / takeover
machinery (Epic 5.2). The only difference is `source` is 'bulk' not 'monitor'.

参考 docs/planning/bulk_send_spec.md §3.4
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models.account import Account
from app.models.bulk_send import (
    BulkBatch, BulkTarget,
    BATCH_RUNNING, BATCH_PAUSED, BATCH_COMPLETED,
    TARGET_SENT, TARGET_DELIVERED, TARGET_REPLIED,
)
from app.models.lead import Lead
from app.services.websocket_manager import manager as ws_manager


logger = logging.getLogger(__name__)


def handle_inbound_dm(
    session: Session,
    account: Account,
    sender_tg_user_id: int,
    sender_username: Optional[str],
    sender_first_name: Optional[str],
    message_text: str,
) -> Optional[Lead]:
    """Check if this DM is a reply to a bulk send; if so, link it.

    Returns the Lead row (created or existing) when it's a bulk reply,
    None otherwise. Idempotent: a second reply from the same sender just
    bumps last_interaction_at and keeps the existing replied state.

    Designed to be safe to call from a hot path (listener) — swallows its
    own errors via try/except in callers.
    """
    if not sender_tg_user_id or not account:
        return None

    # Match scope: a customer-owned account narrows to that customer; pool
    # accounts (customer_id=None) should not produce any bulk-reply because
    # bulk targets are always customer-scoped.
    if not account.customer_id:
        # Pool accounts can still send (mock or real); the target row will
        # have a customer_id, but we have no way to disambiguate at the DM
        # boundary without (assigned_account_id, tg_user_id) matching.
        target = session.exec(
            select(BulkTarget)
            .where(BulkTarget.tg_user_id == sender_tg_user_id)
            .where(BulkTarget.assigned_account_id == account.id)
            .where(BulkTarget.status.in_([TARGET_SENT, TARGET_DELIVERED]))
            .order_by(BulkTarget.sent_at.desc())
            .limit(1)
        ).first()
    else:
        target = session.exec(
            select(BulkTarget)
            .where(BulkTarget.customer_id == account.customer_id)
            .where(BulkTarget.tg_user_id == sender_tg_user_id)
            .where(BulkTarget.status.in_([TARGET_SENT, TARGET_DELIVERED]))
            .order_by(BulkTarget.sent_at.desc())
            .limit(1)
        ).first()

    if not target:
        return None

    batch = session.get(BulkBatch, target.batch_id)
    if not batch:
        return None

    # 1) Mark target as replied (idempotent via status guard above)
    target.status = TARGET_REPLIED
    session.add(target)

    # 2) Bump batch.replied_count
    batch.replied_count = (batch.replied_count or 0) + 1
    batch.updated_at = datetime.utcnow()
    session.add(batch)

    # 3) Upsert Lead — same dedup key as monitor flow (account + tg_user_id)
    lead = session.exec(
        select(Lead)
        .where(Lead.account_id == account.id)
        .where(Lead.telegram_user_id == sender_tg_user_id)
    ).first()

    if not lead:
        # Epic D — inherit industry from parent customer so the sales
        # workbench can group by industry without back-filling.
        from app.models.customer import Customer
        parent = session.get(Customer, batch.customer_id)
        industry = parent.industry if parent else None
        lead = Lead(
            account_id=account.id,
            telegram_user_id=sender_tg_user_id,
            username=sender_username,
            first_name=sender_first_name,
            status="replied",
            tags_json=json.dumps(["bulk_reply"]),
            last_interaction_at=datetime.utcnow(),
            customer_id=batch.customer_id,
            source="bulk",
            bulk_batch_id=batch.id,
            industry=industry,
        )
        session.add(lead)
    else:
        # Existing lead — bump interaction + flip source if previously monitor
        lead.last_interaction_at = datetime.utcnow()
        lead.status = "replied"
        if lead.source != "bulk":
            lead.source = "bulk"
            lead.bulk_batch_id = batch.id
        try:
            tags = json.loads(lead.tags_json or "[]")
            if "bulk_reply" not in tags:
                tags.append("bulk_reply")
                lead.tags_json = json.dumps(tags)
        except (json.JSONDecodeError, TypeError):
            lead.tags_json = json.dumps(["bulk_reply"])
        session.add(lead)

    session.commit()
    session.refresh(lead)

    # 4) Broadcast WS event so any open Portal /bulk/inbox refreshes live
    payload = {
        "type": "bulk_reply",
        "batch_id": batch.id,
        "batch_name": batch.name,
        "customer_id": batch.customer_id,
        "lead_id": lead.id,
        "sender_tg_user_id": sender_tg_user_id,
        "sender_first_name": sender_first_name,
        "message_preview": (message_text or "")[:200],
    }
    try:
        # Listener is async, so this works inline. If called from sync code
        # (e.g. a Celery task), schedule on a new event loop.
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(ws_manager.broadcast(payload), loop=loop)
        except RuntimeError:
            asyncio.run(ws_manager.broadcast(payload))
    except Exception as e:
        logger.warning(f"bulk_reply WS broadcast failed: {e}")

    logger.info(
        f"bulk_reply: batch={batch.id} target={target.id} → lead {lead.id} "
        f"(customer {batch.customer_id})"
    )
    return lead
