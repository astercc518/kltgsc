"""
Weekly batch: discover new candidate groups for all active customers.

NOTE: This task uses asyncio.run(), which requires Celery's default `prefork`
pool.  If the worker is started with ``--pool=gevent`` or ``--pool=eventlet``
this will raise RuntimeError at runtime.  Configure Celery deployment to use
prefork (the default) for the queue that handles group_discovery.weekly.
"""
import asyncio
import logging

from app.core.celery_app import celery_app
from app.services.group_discovery_service import discover_for_all_active_customers

logger = logging.getLogger(__name__)


@celery_app.task(name="group_discovery.weekly")
def discover_weekly():
    result = asyncio.run(discover_for_all_active_customers())
    logger.info("group_discovery weekly: %s", result)
    return result
