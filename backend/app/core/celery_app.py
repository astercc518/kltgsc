from celery import Celery
from kombu import Queue
from app.core.config import settings

celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    # 序列化配置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # ==================== 可靠性配置 ====================
    # 任务完成后才确认，防止 worker 崩溃导致任务丢失
    task_acks_late=True,
    
    # Worker 异常退出时拒绝正在处理的任务，让其他 worker 重新处理
    task_reject_on_worker_lost=True,
    
    # 结果过期时间 (24小时)
    result_expires=86400,
    
    # ==================== 重试配置 ====================
    # 默认重试延迟 (60秒)
    task_default_retry_delay=60,
    
    # 最大重试次数
    task_max_retries=3,
    
    # 启动时重试连接 broker
    broker_connection_retry_on_startup=True,
    
    # ==================== 性能配置 ====================
    # Worker 预取倍数 (每次从队列获取的任务数)
    worker_prefetch_multiplier=4,
    
    # 禁用心跳 (使用 Redis 时可以禁用以减少连接)
    broker_heartbeat=0,
    
    # 连接池大小
    broker_pool_limit=10,
    
    # ==================== 队列配置 ====================
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('high_priority', routing_key='high'),
        Queue('low_priority', routing_key='low'),
    ),
    task_default_queue='default',
    task_default_routing_key='default',
    
    # ==================== 任务路由 ====================
    task_routes={
        # 高优先级任务
        'app.tasks.account_tasks.check_account_status': {'queue': 'high_priority'},
        'app.tasks.monitor_tasks.execute_shill_conversation': {'queue': 'high_priority'},

        # 低优先级任务
        'app.tasks.marketing_tasks.execute_warmup_task': {'queue': 'low_priority'},
        'app.tasks.proxy_tasks.check_proxies_batch_task': {'queue': 'low_priority'},
    },

    # ==================== 并发限制 ====================
    # 任务级别的速率限制
    task_annotations={
        'app.tasks.marketing_tasks.execute_send_task': {'rate_limit': '10/m'},  # 每分钟最多10个
        'app.tasks.account_tasks.check_account_status': {'rate_limit': '30/m'},  # 每分钟最多30个
        'app.tasks.scraping_tasks.scrape_members_batch_task': {'rate_limit': '5/m'},  # 每分钟最多5个
    },
    
    # ==================== 监控配置 ====================
    # 发送任务状态事件
    worker_send_task_events=True,
    
    # 任务结果追踪
    task_track_started=True,
)


# 自定义任务基类，添加通用异常处理
from celery import Task
import logging

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """自定义任务基类，添加通用异常处理和重试逻辑"""
    
    # 自动重试的异常类型
    autoretry_for = (ConnectionError, TimeoutError)
    
    # 重试延迟使用指数退避
    retry_backoff = True
    retry_backoff_max = 600  # 最大10分钟
    retry_jitter = True  # 添加随机抖动避免惊群效应
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的回调"""
        logger.error(
            f"Task {self.name}[{task_id}] failed: {exc}\n"
            f"Args: {args}\nKwargs: {kwargs}\n"
            f"Exception info: {einfo}"
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试时的回调"""
        logger.warning(
            f"Task {self.name}[{task_id}] retrying due to: {exc}\n"
            f"Args: {args}"
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的回调"""
        logger.info(f"Task {self.name}[{task_id}] completed successfully")
        super().on_success(retval, task_id, args, kwargs)


# 设置默认任务基类
celery_app.Task = BaseTask
