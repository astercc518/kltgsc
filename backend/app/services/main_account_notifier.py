"""
Epic 5.2 — Notify a customer's main account about high-intent leads.

The notification is sent as a regular Telegram message to "me" (the main
account's own Saved Messages) so it surfaces as a normal mobile push without
adding a 3rd-party bot to their contacts.

If the main account session is dead (AuthKeyUnregistered, etc.), we fall
back to a ws_manager broadcast so the customer's portal session still gets
the alert.

Wrapped as a Celery task so the AI reply pipeline can fire-and-forget; the
task is best-effort — failure never blocks the upstream pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.account import Account
from app.models.customer import Customer
from app.models.lead import Lead

logger = logging.getLogger(__name__)


def _format_notification(lead: Lead, customer_id: int) -> str:
    """Compose the message body sent to the customer's Saved Messages."""
    name = (lead.first_name or "") + (f" @{lead.username}" if lead.username else "")
    name = name.strip() or f"TG user {lead.telegram_user_id}"
    tags = ""
    try:
        import json as _json
        t = _json.loads(lead.tags_json or "[]")
        if t:
            tags = f"\n🏷  {', '.join(t)}"
    except Exception:
        pass
    deadline = ""
    if lead.takeover_deadline:
        # Format as local-time-ish; client renders it
        deadline = f"\n⏰ Take over before: {lead.takeover_deadline.isoformat()} UTC"
    body = (
        f"🔥 TG1.AI: high-intent prospect\n\n"
        f"👤 {name}\n"
        f"💬 Status: {lead.status}{tags}{deadline}\n\n"
        f"Open Inbox to take over:\n"
        f"https://tg1.ai/portal/leads/{lead.id}\n\n"
        f"If you don't take over before the deadline, AI will send the prospect "
        f"your handover-group link automatically."
    )
    return body


async def _send_via_main_account(account: Account, body: str) -> bool:
    """Drive a one-shot Pyrogram client off the encrypted session_string."""
    if not account.session_string:
        return False
    try:
        from pyrogram import Client
        from pyrogram.errors import AuthKeyUnregistered, UserDeactivated
    except ImportError:
        return False

    # Decrypt the session string transparently
    from app.core.encryption import decrypt_session_string
    plain_session = decrypt_session_string(account.session_string)

    # api_id / api_hash from system_config
    from app.models.system_config import SystemConfig
    with Session(engine) as s:
        from sqlmodel import select
        api_id_row = s.exec(select(SystemConfig).where(SystemConfig.key == "api_id")).first()
        api_hash_row = s.exec(select(SystemConfig).where(SystemConfig.key == "api_hash")).first()
        api_id = int(api_id_row.value) if api_id_row and api_id_row.value else 0
        api_hash = api_hash_row.value if api_hash_row else ""

    if not api_id or not api_hash:
        logger.warning("notifier: api_id/api_hash not configured, cannot send via main account")
        return False

    if plain_session.startswith("MOCK_SESSION_"):
        # MOCK mode: skip actual Pyrogram, just log
        logger.info("notifier: MOCK main_account=%s would send:\n%s",
                    account.id, body[:200])
        return True

    client = Client(
        name=f"notify_{account.id}",
        api_id=api_id, api_hash=api_hash,
        session_string=plain_session,
        in_memory=True,
    )
    try:
        await client.start()
        await client.send_message("me", body)
        await client.stop()
        return True
    except (AuthKeyUnregistered, UserDeactivated) as e:
        logger.warning("notifier: main account %s session dead: %s", account.id, e)
        return False
    except Exception as e:  # noqa: BLE001
        logger.exception("notifier: send via main account %s failed: %s", account.id, e)
        try:
            await client.stop()
        except Exception:
            pass
        return False


def _fallback_ws_broadcast(lead: Lead, customer_id: int, body: str) -> None:
    """If the main account is unreachable, push to the portal WS instead."""
    try:
        from app.services.websocket_manager import ws_manager
    except Exception:
        return
    try:
        asyncio.run(ws_manager.broadcast({
            "type": "main_account_notification_fallback",
            "data": {
                "customer_id": customer_id,
                "lead_id": lead.id,
                "body": body,
            },
        }))
    except Exception as e:  # noqa: BLE001
        logger.debug("notifier: ws fallback also failed: %s", e)


@celery_app.task(
    bind=True, name="app.services.main_account_notifier.notify_high_intent",
    max_retries=2, default_retry_delay=30,
)
def notify_high_intent(self, lead_id: int) -> dict:
    """Send a Saved-Messages notification to the customer's main account.

    Idempotent: only fires when lead.main_account_notified_at IS NULL.
    """
    with Session(engine) as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            return {"sent": False, "reason": "lead not found"}
        if lead.main_account_notified_at is not None:
            return {"sent": False, "reason": "already notified"}
        if not lead.customer_id:
            return {"sent": False, "reason": "lead has no customer"}

        customer = s.get(Customer, lead.customer_id)
        if not customer or not customer.notify_main_account:
            return {"sent": False, "reason": "customer opted out"}
        if not customer.main_account_id:
            # No main account bound; fallback path only
            body = _format_notification(lead, customer.id)
            _fallback_ws_broadcast(lead, customer.id, body)
            lead.main_account_notified_at = datetime.utcnow()
            s.add(lead); s.commit()
            return {"sent": True, "via": "ws_fallback"}

        main = s.get(Account, customer.main_account_id)
        if not main or not main.is_customer_main:
            return {"sent": False, "reason": "main account missing/invalid"}

        body = _format_notification(lead, customer.id)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ok = loop.run_until_complete(_send_via_main_account(main, body))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if not ok:
            _fallback_ws_broadcast(lead, customer.id, body)

        lead.main_account_notified_at = datetime.utcnow()
        s.add(lead); s.commit()
        return {"sent": True, "via": "main_account" if ok else "ws_fallback"}
