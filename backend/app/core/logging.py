"""
日志系统配置
提供集中化的日志配置和格式化
"""
import os
import sys
import logging
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional
from pathlib import Path


# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器，适用于日志聚合系统"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
            
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式化器"""
    
    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[41m",  # 红色背景
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    json_format: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    配置全局日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否写入文件
        log_to_console: 是否输出到控制台
        json_format: 是否使用 JSON 格式 (适用于日志聚合)
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 格式定义
    detailed_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    simple_format = "%(asctime)s - %(levelname)s - %(message)s"
    
    # 控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        if json_format:
            console_handler.setFormatter(JSONFormatter())
        else:
            # 检查是否支持彩色输出
            if sys.stdout.isatty():
                console_handler.setFormatter(
                    ColoredFormatter(simple_format)
                )
            else:
                console_handler.setFormatter(
                    logging.Formatter(simple_format)
                )
        
        root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_to_file:
        # 主日志文件 (按大小轮转)
        main_log_path = LOG_DIR / "tgsc.log"
        file_handler = RotatingFileHandler(
            main_log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        
        if json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(detailed_format))
        
        root_logger.addHandler(file_handler)
        
        # 错误日志文件 (仅记录 ERROR 及以上)
        error_log_path = LOG_DIR / "error.log"
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(detailed_format))
        root_logger.addHandler(error_handler)
        
        # 每日审计日志 (按日期轮转)
        audit_log_path = LOG_DIR / "audit.log"
        audit_handler = TimedRotatingFileHandler(
            audit_log_path,
            when="midnight",
            interval=1,
            backupCount=30,  # 保留30天
            encoding="utf-8"
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(logging.Formatter(detailed_format))
        
        # 只记录特定的审计日志
        audit_filter = AuditLogFilter()
        audit_handler.addFilter(audit_filter)
        root_logger.addHandler(audit_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    root_logger.info("Logging system initialized")


class AuditLogFilter(logging.Filter):
    """审计日志过滤器，只记录与安全/操作相关的日志"""
    
    AUDIT_KEYWORDS = [
        "login",
        "logout",
        "auth",
        "session",
        "account",
        "delete",
        "create",
        "update",
        "import",
        "export",
        "encrypt",
        "decrypt",
        "permission",
        "access",
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        return any(keyword in message for keyword in self.AUDIT_KEYWORDS)


class TaskLogger:
    """任务专用日志器，用于 Celery 任务"""
    
    def __init__(self, task_name: str, task_id: Optional[str] = None):
        self.logger = logging.getLogger(f"task.{task_name}")
        self.task_name = task_name
        self.task_id = task_id
        
    def _format_message(self, message: str) -> str:
        if self.task_id:
            return f"[{self.task_id}] {message}"
        return message
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(self._format_message(message), **kwargs)
        
    def info(self, message: str, **kwargs):
        self.logger.info(self._format_message(message), **kwargs)
        
    def warning(self, message: str, **kwargs):
        self.logger.warning(self._format_message(message), **kwargs)
        
    def error(self, message: str, **kwargs):
        self.logger.error(self._format_message(message), **kwargs)
        
    def exception(self, message: str, **kwargs):
        self.logger.exception(self._format_message(message), **kwargs)


def get_task_logger(task_name: str, task_id: Optional[str] = None) -> TaskLogger:
    """获取任务日志器"""
    return TaskLogger(task_name, task_id)


# 初始化日志系统
def init_logging():
    """在应用启动时调用"""
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    json_logs = os.environ.get("JSON_LOGS", "false").lower() == "true"
    
    setup_logging(
        level=log_level,
        log_to_file=True,
        log_to_console=True,
        json_format=json_logs
    )
