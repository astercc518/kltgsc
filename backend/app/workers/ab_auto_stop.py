"""Celery beat task: daily auto-stop check"""
import logging

from app.core.celery_app import celery_app
from app.services.ab_auto_stop_service import run_auto_stop_check

logger = logging.getLogger(__name__)


@celery_app.task(name="ab_auto_stop.daily_check")
def auto_stop_daily():
    stopped = run_auto_stop_check()
    logger.info("ab_auto_stop daily check: stopped %d experiments", stopped)
    return stopped
