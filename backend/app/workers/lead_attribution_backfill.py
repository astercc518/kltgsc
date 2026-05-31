"""Celery beat task: Phase 11 lead attribution backfill.

Periodically sweeps recent SENT PendingReply rows whose lead_id is still NULL
and tries to attach them to a Lead inside the attribution window. The window
in lead_attribution_service defaults to 24h, so a 30-minute beat cadence
gives every reply roughly 48 chances to find its Lead within window.

prefork queue only — service uses synchronous SQLModel session.
"""
import logging

from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.db import engine
from app.services.lead_attribution_service import backfill_unlinked_replies

logger = logging.getLogger(__name__)


@celery_app.task(name="lead_attribution.backfill")
def lead_attribution_backfill_tick() -> int:
    """Run one backfill pass. Returns the number of replies linked."""
    with Session(engine) as session:
        linked = backfill_unlinked_replies(session)
    logger.info("lead_attribution.backfill: linked %d replies", linked)
    return linked
