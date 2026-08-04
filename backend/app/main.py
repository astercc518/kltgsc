import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from app.core.config import Environment, settings
from app.api.v1 import router as api_router
from app.core.db import init_db as init_tables, engine
from app.db.init_db import init_db as seed_db
from app.core.middleware import SecurityMiddleware
from app.core.exceptions import register_exception_handlers
from app.core.logging import init_logging

# 初始化日志系统
init_logging()

logger = logging.getLogger(__name__)


def should_create_tables() -> bool:
    """Local development may bootstrap tables; production uses Alembic only."""
    return settings.ENVIRONMENT != Environment.PRODUCTION


def should_warmup_moderator() -> bool:
    """Allow tests and constrained processes to skip loading the ONNX model."""
    return settings.LLM_SAFETY_WARMUP


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create DB tables
    logger.info("Starting TGSC Backend...")
    if should_create_tables():
        init_tables()
    # Seed initial admin user
    with Session(engine) as session:
        seed_db(session)
    # Warm up L1 moderation (ONNX model load) — otherwise first request blocks
    # for several seconds. Fail-open: if model unavailable, _safety_check
    # falls back to L0-only and logs a warning per request.
    if should_warmup_moderator():
        try:
            from app.services.safety.moderation import Moderator
            Moderator.warmup()
            logger.info("L1 moderation model warmed up")
        except Exception as e:
            logger.warning(f"L1 moderation warmup failed (fail-open, L0-only): {e}")
    logger.info(f"TGSC Backend started. Security enabled: {settings.SECURITY_ENABLED}")
    yield
    # Shutdown events
    logger.info("Shutting down TGSC Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    docs_url="/api/docs" if not settings.SECURITY_ENABLED else None,  # 生产环境禁用文档
    redoc_url="/api/redoc" if not settings.SECURITY_ENABLED else None,
)

# 注册标准化异常处理器
register_exception_handlers(app)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    # 处理字符串或列表格式的 CORS 配置
    if isinstance(settings.BACKEND_CORS_ORIGINS, str):
        cors_origins = [origin.strip() for origin in settings.BACKEND_CORS_ORIGINS.split(",")]
    else:
        cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 添加安全中间件
app.add_middleware(SecurityMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    logger.warning(f"Validation Error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "请求参数验证失败",
            "details": {"errors": exc.errors()}
        },
    )


@app.get("/api/v1/health")
def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "message": "Backend is running",
        "security_enabled": settings.SECURITY_ENABLED
    }


app.include_router(api_router, prefix=settings.API_V1_STR)
