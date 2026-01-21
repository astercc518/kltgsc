from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from app.core.config import settings
from app.api.v1 import router as api_router
from app.core.db import init_db as init_tables, engine
from app.db.init_db import init_db as seed_db
from app.core.middleware import SecurityMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create DB tables
    init_tables()
    # Seed initial admin user
    with Session(engine) as session:
        seed_db(session)
    yield
    # Shutdown events if any

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

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
    # Print simplified errors to logs
    print(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation Error", "errors": str(exc.errors())},
    )

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "message": "Backend is running"}

app.include_router(api_router, prefix=settings.API_V1_STR)
