"""
join_attempt_scanner — Celery beat task for processing pending join_attempts.

NOTE: This worker requires the Celery prefork pool (the default) so that
asyncio.run() in scan_tick() launches a fresh event loop per call — the
same pattern used by group_reply_scanner.py and chitchat_scheduler.py.
Do NOT run this on a gevent/eventlet pool.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.celery_app import celery_app
from app.core.db import engine
from app.models.join_attempt import JoinAttempt

logger = logging.getLogger(__name__)

# Only pick up attempts that have been waiting at least this long (avoids
# racing with a fresh insert that hasn't been processed yet).
_DELAY_SECONDS = 10


async def scan_and_process() -> int:
    """
    Fetch pending + captcha-state join_attempts older than _DELAY_SECONDS
    and call process_attempt() on each.  Returns the number of attempts
    dispatched.
    """
    from app.services.join_orchestrator import process_attempt  # local import avoids circular dep

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_DELAY_SECONDS)
    with Session(engine) as session:
        ids = list(
            session.exec(
                select(JoinAttempt.id).where(
                    JoinAttempt.status.in_(["pending", "captcha"]),  # type: ignore[union-attr]
                    JoinAttempt.updated_at <= cutoff,
                ).limit(50)
            ).all()
        )

    if not ids:
        return 0

    logger.info("join_attempt_scanner: processing %d attempts", len(ids))
    n = 0
    for attempt_id in ids:
        try:
            await process_attempt(attempt_id=attempt_id)
            n += 1
        except Exception:
            logger.exception("join_attempt_scanner: failed for attempt_id=%s", attempt_id)
    return n


@celery_app.task(name="join_attempt.scan")
def scan_tick():
    """Celery beat entry point: runs the async scanner in a fresh event loop."""
    return asyncio.run(scan_and_process())
