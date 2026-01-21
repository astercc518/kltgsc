from typing import Optional
from sqlmodel import Session
from app.models.system_config import SystemConfig

def get_system_config_value(session: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    """获取系统配置值"""
    config = session.get(SystemConfig, key)
    if config:
        return config.value
    return default
