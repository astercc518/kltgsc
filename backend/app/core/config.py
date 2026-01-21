from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Telegram SC Platform"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Admin User
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    
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

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

settings = Settings()
