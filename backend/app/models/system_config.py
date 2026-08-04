from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class SystemConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SystemConfigRead(SQLModel):
    key: str
    value: Optional[str]
    description: Optional[str]
    updated_at: datetime
    is_sensitive: bool
    is_configured: bool


SENSITIVE_CONFIG_MARKERS = (
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "API_KEY",
    "PRIVATE_KEY",
    "ENCRYPTION_KEY",
)


def redact_system_config(config: SystemConfig) -> SystemConfigRead:
    normalized_key = config.key.upper()
    is_sensitive = any(
        marker in normalized_key for marker in SENSITIVE_CONFIG_MARKERS
    )
    return SystemConfigRead(
        key=config.key,
        value=None if is_sensitive else config.value,
        description=config.description,
        updated_at=config.updated_at,
        is_sensitive=is_sensitive,
        is_configured=bool(config.value),
    )
