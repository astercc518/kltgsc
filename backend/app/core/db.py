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
    engine = create_engine(
        settings.DATABASE_URL, 
        echo=False,
        pool_size=20,           # 连接池大小
        max_overflow=30,        # 超出 pool_size 后最多可创建的连接数
        pool_pre_ping=True,     # 自动检测失效连接
        pool_recycle=3600       # 1小时回收连接
    )

def init_db():
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
