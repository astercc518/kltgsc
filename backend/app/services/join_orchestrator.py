"""
join_orchestrator — 加群编排.

调用时机:
  - Phase 7 portal_discovery.approve_candidate 调 queue_join()
  - admin 手工触发也调 queue_join()

Celery beat scanner 处理 status='pending' 的行.

状态机:
  pending  → joining: telethon JoinChannelRequest sent
  joining  → captcha: detector 返回非 'no_captcha'
  captcha  → joined: handler success + 能发言
  joining  → joined: 直接成功 (no captcha)
  captcha  → failed: handler 失败 N 次 (3)
  joining/captcha → failed: telethon 异常 / chat 私有不可达
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from app.core.db import engine
from app.models.captcha_event import CaptchaEvent
from app.models.join_attempt import (
    JoinAttempt,
    STATUS_CAPTCHA,
    STATUS_FAILED,
    STATUS_JOINED,
    STATUS_PENDING,
)

logger = logging.getLogger(__name__)

MAX_CAPTCHA_ATTEMPTS = 3


def queue_join(
    *,
    customer_id: int,
    account_id: int,
    chat_link: str,
    discovered_group_id: Optional[int] = None,
) -> int:
    """Insert a pending join_attempt row. Returns join_attempt.id."""
    now = datetime.now(timezone.utc)
    attempt = JoinAttempt(
        customer_id=customer_id,
        account_id=account_id,
        chat_link=chat_link,
        discovered_group_id=discovered_group_id,
        status=STATUS_PENDING,
        captcha_attempts=0,
        created_at=now,
        updated_at=now,
    )
    with Session(engine) as session:
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
    logger.info(
        "queue_join: id=%s customer=%s account=%s link=%s",
        attempt.id, customer_id, account_id, chat_link,
    )
    return attempt.id


async def process_attempt(*, attempt_id: int) -> str:
    """
    Process one join_attempt end-to-end. Returns final status string.

    Single-session pattern to avoid TOCTOU race: status read + update happen
    inside the same session so no other worker can interleave between the
    status check and the write.

    Phase 8 v1: Telethon client integration is a placeholder stub.
    The real implementation must be wired to the existing listener_service
    client management once client references are available.

    实施者: 这部分 Telethon 集成需要根据现有 listener_service 的 client 管理
    方式来实现. 简化伪代码:

      client = await get_telethon_client(account_id)
      await client(JoinChannelRequest(chat_link))
      _update_attempt(attempt_id=attempt_id, status=STATUS_JOINING)
      await asyncio.sleep(10)
      msgs = await client.get_messages(chat_link, limit=5)
      structured = [{"text": m.text, "buttons": [...], "has_photo": bool(m.photo), ...} ...]
      detection = detect_captcha_type(recent_messages=structured, admin_dms_after_join=[])

      if detection['type'] == 'no_captcha':
          _update_attempt(attempt_id=attempt_id, status=STATUS_JOINED)
          return STATUS_JOINED

      _update_attempt(attempt_id=attempt_id, status=STATUS_CAPTCHA,
                      captcha_type=detection['type'])

      # dispatch handler by captcha type, call _insert_captcha_event, etc.
      # on success: STATUS_JOINED; on repeated failure: STATUS_FAILED
    """
    with Session(engine) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        if attempt is None:
            logger.warning("process_attempt: attempt_id=%s not found", attempt_id)
            return "not_found"
        if attempt.status not in (STATUS_PENDING, STATUS_CAPTCHA):
            logger.info(
                "process_attempt: attempt_id=%s already in status=%s, skipping",
                attempt_id, attempt.status,
            )
            return attempt.status

        # Phase 8 v1 placeholder — Telethon integration wired in follow-up PR.
        # Mark as failed so the failure queue surfaces it for manual review.
        logger.info(
            "process_attempt: attempt_id=%s — Telethon integration pending, marking failed",
            attempt_id,
        )
        attempt.status = STATUS_FAILED
        attempt.last_error = "telethon_integration_pending"
        attempt.updated_at = datetime.now(timezone.utc)
        session.add(attempt)

        evt = CaptchaEvent(
            join_attempt_id=attempt_id,
            handler="placeholder",
            succeeded=False,
            error_message="telethon_integration_pending",
            created_at=datetime.now(timezone.utc),
        )
        session.add(evt)

        session.commit()
        return STATUS_FAILED


def _update_attempt(*, attempt_id: int, **fields) -> None:
    """Sync helper: update arbitrary fields on a JoinAttempt row."""
    with Session(engine) as session:
        attempt = session.get(JoinAttempt, attempt_id)
        if attempt is None:
            logger.warning("_update_attempt: attempt_id=%s not found", attempt_id)
            return
        for k, v in fields.items():
            setattr(attempt, k, v)
        attempt.updated_at = datetime.now(timezone.utc)
        session.add(attempt)
        session.commit()


def _insert_captcha_event(
    *,
    join_attempt_id: int,
    handler: str,
    succeeded: bool,
    input_summary: str = "",
    output_summary: str = "",
    error_message: Optional[str] = None,
    metadata_json: Optional[dict] = None,
) -> None:
    """Sync helper: write a CaptchaEvent audit row."""
    with Session(engine) as session:
        evt = CaptchaEvent(
            join_attempt_id=join_attempt_id,
            handler=handler,
            input_summary=input_summary,
            output_summary=output_summary,
            succeeded=succeeded,
            error_message=error_message,
            metadata_json=metadata_json,
            created_at=datetime.now(timezone.utc),
        )
        session.add(evt)
        session.commit()
