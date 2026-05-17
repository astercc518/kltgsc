from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# 根据数据库类型配置连接参数
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite 需要特殊处理多线程
    connect_args = {"check_same_thread": False}
    engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
else:
    # PostgreSQL - 使用连接池
    # 1000+ 账号规模下，进程数 ≈ 14 (4 gunicorn + 8 celery worker + 1 beat + 1 listener)。
    # 每进程 10+10 = 20 连接，理论上限 14*20 = 280，PG 侧 max_connections=500 留余量。
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
    )

def init_db():
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
