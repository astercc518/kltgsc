import secrets
from enum import Enum
from typing import List, Union
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


_KNOWN_DEFAULT_PASSWORDS = {
    "123456",
    "admin123",
    "changeme",
    "change_me",
    "password",
    "password123!",
    # Retired production default. Keep the fingerprint split so repository
    # scanners can reject the literal wherever it is accidentally reintroduced.
    "admin@" "tgsc2026",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "Telegram SC Platform"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    COMPOSE_DEPLOYMENT: bool = False
    LLM_SAFETY_WARMUP: bool = True
    
    # 安全配置 - production 必须显式设置
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Session 加密密钥 (用于加密 .session 文件)
    SESSION_ENCRYPTION_KEY: str = Field(default="")
    
    # Admin User - 生产环境必须修改
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = Field(default="")
    
    # 安全模式 - 生产环境设为 True
    SECURITY_ENABLED: bool = Field(default=True)
    
    # Database
    DATABASE_URL: str = "sqlite:///./tgsc.db"
    
    # CORS - 支持字符串或列表
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # External Services
    SMS_ACTIVATE_API_KEY: str = ""
    IP2WORLD_API_URL: str = ""
    DEFAULT_2FA_PASSWORD: str = "Password123!"

    # ── TG1.AI Subscription billing (Epic 2, USDT) ───────────────────
    # 客户付款收款地址：每条链一个静态地址，由 ops 手动维护
    USDT_ADDRESS_TRC20: str = ""
    USDT_ADDRESS_ERC20: str = ""
    USDT_ADDRESS_BEP20: str = ""
    # Invoice 过期时间（分钟）— 超时未付款自动 expire，需重新下单
    INVOICE_EXPIRE_MINUTES: int = 30
    # NowPayments IPN secret (Epic 2.5)；为空 = webhook 关闭，仍走 admin 手动激活
    NOWPAYMENTS_IPN_SECRET: str = ""
    
    @model_validator(mode="after")
    def validate_runtime_security(self) -> "Settings":
        """Generate silent local credentials or fail closed in production."""
        if self.ENVIRONMENT != Environment.PRODUCTION:
            if len(self.SECRET_KEY) < 32:
                self.SECRET_KEY = secrets.token_hex(32)
            if len(self.SESSION_ENCRYPTION_KEY) < 32:
                self.SESSION_ENCRYPTION_KEY = secrets.token_hex(32)
            if len(self.ADMIN_PASSWORD) < 12:
                self.ADMIN_PASSWORD = secrets.token_urlsafe(18)
            return self

        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if len(self.SESSION_ENCRYPTION_KEY) < 32:
            raise ValueError(
                "SESSION_ENCRYPTION_KEY must be at least 32 characters in production"
            )
        if not self.SECURITY_ENABLED:
            raise ValueError("SECURITY_ENABLED must be true in production")

        normalized_password = self.ADMIN_PASSWORD.strip().lower()
        if (
            len(self.ADMIN_PASSWORD) < 12
            or normalized_password in _KNOWN_DEFAULT_PASSWORDS
            or "change_me" in normalized_password
            or "replace" in normalized_password
            or normalized_password.startswith("<")
        ):
            raise ValueError("ADMIN_PASSWORD is missing, weak, or a known default")

        database_scheme = urlparse(self.DATABASE_URL).scheme.lower()
        if not database_scheme.startswith("postgresql"):
            raise ValueError("DATABASE_URL must use PostgreSQL in production")

        redis_url = urlparse(self.REDIS_URL)
        if redis_url.scheme.lower() not in {"redis", "rediss"} or not redis_url.hostname:
            raise ValueError("REDIS_URL must be a valid Redis URL in production")
        if self.COMPOSE_DEPLOYMENT and not redis_url.password:
            raise ValueError("REDIS_URL must include authentication for Compose production")
        return self

    # ── RAG Reranker (cross-encoder post-step for kb_retrieval) ──────
    # Default OFF; flip to true after staging validation. See
    # docs/ai_reply/reranker.md for rollout guidance.
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    # Number of pgvector candidates fetched per query = top_k * multiplier
    RERANK_CANDIDATE_MULTIPLIER: int = 5
    # Hard timeout for one rerank call; on timeout we drop back to cosine order
    RERANK_TIMEOUT_MS: int = 800

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")


settings = Settings()
