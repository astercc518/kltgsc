"""
Celery worker entry point.
Imports all tasks so they are registered with Celery.

All task implementations live in app/tasks/ submodules.
This file exists solely to serve as the Celery worker entry point
and to ensure every task is discovered and registered.
"""
from app.core.celery_app import celery_app

# Import all task modules to register them with Celery
from app.tasks.account_tasks import *   # noqa: F401,F403
from app.tasks.marketing_tasks import * # noqa: F401,F403
from app.tasks.invite_tasks import *    # noqa: F401,F403
from app.tasks.scraping_tasks import *  # noqa: F401,F403
from app.tasks.monitor_tasks import *   # noqa: F401,F403
from app.tasks.proxy_tasks import *     # noqa: F401,F403
