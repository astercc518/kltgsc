"""
任务模块
按功能拆分 Celery 任务
"""
from app.tasks.account_tasks import (
    check_account_status,
    import_mega_accounts,
    create_warmup_after_imports,
)
from app.tasks.marketing_tasks import (
    execute_send_task,
    execute_warmup_task,
    check_auto_reply_task,
    execute_script_task,
)
from app.tasks.scraping_tasks import (
    join_groups_batch_task,
    scrape_members_batch_task,
)
from app.tasks.proxy_tasks import (
    check_proxies_batch_task,
)
from app.tasks.monitor_tasks import (
    execute_shill_conversation,
)
from app.tasks.invite_tasks import (
    execute_invite_task,
)

__all__ = [
    # Account tasks
    "check_account_status",
    "import_mega_accounts",
    "create_warmup_after_imports",
    # Marketing tasks
    "execute_send_task",
    "execute_warmup_task",
    "check_auto_reply_task",
    "execute_script_task",
    # Scraping tasks
    "join_groups_batch_task",
    "scrape_members_batch_task",
    # Proxy tasks
    "check_proxies_batch_task",
    # Monitor tasks
    "execute_shill_conversation",
    # Invite tasks
    "execute_invite_task",
]
