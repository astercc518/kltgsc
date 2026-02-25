import os
import secrets
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


def generate_secret_key() -> str:
    """生成安全的 SECRET_KEY，优先从环境变量读取"""
    env_key = os.environ.get("SECRET_KEY")
    if env_key and len(env_key) >= 32:
        return env_key
    # 生成新的密钥并警告
    new_key = secrets.token_hex(32)
    print(f"⚠️ WARNING: SECRET_KEY not set in environment! Using generated key.")
    print(f"⚠️ For production, set SECRET_KEY={new_key} in .env file")
    return new_key


class Settings(BaseSettings):
    PROJECT_NAME: str = "Telegram SC Platform"
    API_V1_STR: str = "/api/v1"
    
    # 安全配置 - SECRET_KEY 必须从环境变量设置
    SECRET_KEY: str = Field(default_factory=generate_secret_key)
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
    
    @field_validator("ADMIN_PASSWORD", mode="before")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        """验证管理员密码安全性"""
        if not v or v in ["", "admin123", "password", "123456"]:
            # 生成安全的随机密码
            new_password = secrets.token_urlsafe(16)
            print(f"⚠️ WARNING: ADMIN_PASSWORD not set or too weak!")
            print(f"⚠️ Generated secure password: {new_password}")
            print(f"⚠️ Set ADMIN_PASSWORD={new_password} in .env file")
            return new_password
        if len(v) < 12:
            print(f"⚠️ WARNING: ADMIN_PASSWORD should be at least 12 characters!")
        return v
    
    @field_validator("SESSION_ENCRYPTION_KEY", mode="before")
    @classmethod
    def validate_session_key(cls, v: str) -> str:
        """确保 Session 加密密钥存在"""
        if not v or len(v) < 32:
            # 生成 32 字节的加密密钥 (256-bit AES)
            new_key = secrets.token_hex(16)  # 32 hex chars = 16 bytes = 128-bit
            print(f"⚠️ WARNING: SESSION_ENCRYPTION_KEY not set!")
            print(f"⚠️ Set SESSION_ENCRYPTION_KEY={new_key} in .env file")
            return new_key
        return v

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")


settings = Settings()
