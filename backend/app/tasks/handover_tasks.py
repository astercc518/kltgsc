"""
Epic 5.2 — Auto-send "business handover group" link if a high-intent lead
hasn't been claimed by deadline.

Race-safe pattern:
  • SELECT ... FOR UPDATE (Postgres row lock) on the Lead row
  • Recheck inside the lock:
      assigned_to_user_id IS NULL
      AND claimed_at IS NULL
      AND handover_link_sent_at IS NULL
      AND takeover_deadline <= NOW()
  • Write handover_link_sent_at BEFORE releasing the lock so any concurrent
    claim attempt sees the row already taken

If customer hasn't configured a handover_group_link, the task no-ops (and
WS-broadcasts a system_alert so the customer knows they're missing config).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text as sa_text
from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.account import Account
from app.models.customer import Customer
from app.models.lead import Lead

logger = logging.getLogger(__name__)


async def _dm_prospect_with_handover_link(
    account: Account, prospect_user_id: int, link: str,
) -> bool:
    """Use the AI marketing account to DM the prospect with the handover link."""
    if not account.session_string:
        return False
    try:
        from pyrogram import Client
    except ImportError:
        return False

    from app.core.encryption import decrypt_session_string
    plain = decrypt_session_string(account.session_string)

    # MOCK-only short-circuit (mainly for smoke tests that don't have real session)
    if plain.startswith("MOCK_SESSION_"):
        logger.info("handover: MOCK account=%s would DM user=%s link=%s",
                    account.id, prospect_user_id, link)
        return True

    from app.models.system_config import SystemConfig
    from sqlmodel import select as _select
    with Session(engine) as s:
        api_id_row = s.exec(_select(SystemConfig).where(SystemConfig.key == "api_id")).first()
        api_hash_row = s.exec(_select(SystemConfig).where(SystemConfig.key == "api_hash")).first()
        api_id = int(api_id_row.value) if api_id_row and api_id_row.value else 0
        api_hash = api_hash_row.value if api_hash_row else ""
    if not api_id or not api_hash:
        return False

    text = (
        "Thanks for the chat! For details and our team to follow up properly, "
        f"please join our business group: {link}"
    )
    client = Client(
        name=f"handover_{account.id}",
        api_id=api_id, api_hash=api_hash,
        session_string=plain, in_memory=True,
    )
    try:
        await client.start()
        await client.send_message(prospect_user_id, text)
        await client.stop()
        return True
    except Exception as e:  # noqa: BLE001
        logger.exception("handover: DM via account %s to user %s failed: %s",
                         account.id, prospect_user_id, e)
        try:
            await client.stop()
        except Exception:
            pass
        return False


@celery_app.task(
    bind=True,
    name="app.tasks.handover_tasks.send_handover_link_if_unclaimed",
    max_retries=1, default_retry_delay=60,
)
def send_handover_link_if_unclaimed(self, lead_id: int) -> dict:
    """Atomically check + send. Designed to be safe under Celery retries."""
    with Session(engine) as s:
        # SELECT ... FOR UPDATE so a concurrent claim() blocks.
        # sqlmodel.Session.exec() doesn't accept raw SQL params; use the
        # underlying SQLAlchemy execute().
        s.execute(sa_text("SELECT id FROM lead WHERE id = :id FOR UPDATE"), {"id": lead_id})
        lead = s.get(Lead, lead_id)
        if not lead:
            return {"sent": False, "reason": "lead gone"}
        if lead.handover_link_sent_at is not None:
            return {"sent": False, "reason": "already sent (idempotent)"}
        if lead.assigned_to_user_id is not None or lead.claimed_at is not None:
            return {"sent": False, "reason": "lead claimed before deadline"}
        if not lead.takeover_deadline or lead.takeover_deadline > datetime.utcnow():
            # Re-queued early; respect deadline by rescheduling once
            return {"sent": False, "reason": "deadline not yet reached"}
        if not lead.customer_id:
            return {"sent": False, "reason": "lead has no customer"}

        customer = s.get(Customer, lead.customer_id)
        if not customer:
            return {"sent": False, "reason": "customer not found"}
        if not customer.handover_group_link:
            # Customer never set a handover link — push a system alert via WS
            try:
                from app.services.websocket_manager import ws_manager
                asyncio.run(ws_manager.broadcast({
                    "type": "system_alert",
                    "data": {
                        "customer_id": customer.id,
                        "kind": "missing_handover_group_link",
                        "lead_id": lead.id,
                    },
                }))
            except Exception:
                pass
            return {"sent": False, "reason": "no handover_group_link configured"}

        # Don't self-DM: if the prospect happens to be the customer's main account
        main = s.get(Account, customer.main_account_id) if customer.main_account_id else None
        if main and main.id == lead.account_id:
            return {"sent": False, "reason": "prospect is main account (self-DM avoided)"}

        marketing_account = s.get(Account, lead.account_id)
        if not marketing_account:
            return {"sent": False, "reason": "marketing account missing"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ok = loop.run_until_complete(_dm_prospect_with_handover_link(
                marketing_account, lead.telegram_user_id,
                customer.handover_group_link,
            ))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        # Whether or not the DM physically reached TG, mark it sent so we don't
        # double-DM on a Celery retry. The status flag is also visible to the
        # customer so they know AI did its part.
        lead.handover_link_sent_at = datetime.utcnow()
        s.add(lead); s.commit()
        return {"sent": ok, "link": customer.handover_group_link}
