import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 让 alembic 能找到 app 包（运行目录为 /app）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel  # noqa: E402

# 导入所有模型，触发 SQLModel.metadata 注册
import app.models  # noqa: F401,E402
from app.models import (  # noqa: F401,E402
    Account, Proxy, TargetUser, SystemConfig,
    SendTask, SendRecord, WarmupTask, WarmupTemplate,
    ChatHistory, Script, ScriptTask,
    Lead, LeadInteraction, OperationLog,
    KeywordMonitor, KeywordHit,
    InviteTask, InviteLog, ScrapingTask,
    User, AIConfig, Campaign,
    SourceGroup, FunnelGroup, AIPersona,
    KnowledgeBase, CampaignKnowledgeLink,
    AccountSendStats,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从环境变量覆盖 DATABASE_URL（Docker 环境优先）
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # SQLAlchemy 2.x 要求 postgresql:// 而非 postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = SQLModel.metadata

# 旧版孤立表（已被重命名的历史表）—— autogenerate 时不操作这些表
LEGACY_TABLES = {"aipersona", "funnelgroup", "sourcegroup"}


def include_object(object, name, type_, reflected, compare_to):
    """过滤掉遗留空表，避免 autogenerate 生成 DROP TABLE。"""
    if type_ == "table" and name in LEGACY_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
