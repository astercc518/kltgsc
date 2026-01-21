from sqlmodel import Session, select, text
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.system_config import SystemConfig

def init_db(session: Session) -> None:
    # 检查是否已存在管理员
    user = session.exec(
        select(User).where(User.username == settings.ADMIN_USERNAME)
    ).first()
    
    if not user:
        user = User(
            username=settings.ADMIN_USERNAME,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            is_superuser=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    # Initialize default system configurations
    defaults = {
        "SMS_ACTIVATE_API_KEY": {"value": settings.SMS_ACTIVATE_API_KEY or "", "desc": "SMS-Activate API Key"},
        "IP2WORLD_API_URL": {"value": settings.IP2WORLD_API_URL or "", "desc": "IP2World API URL"},
        "LLM_PROVIDER": {"value": "openai", "desc": "LLM Provider (openai, deepseek, etc.)"},
        "LLM_API_KEY": {"value": "", "desc": "LLM API Key"},
        "LLM_BASE_URL": {"value": "https://api.openai.com/v1", "desc": "LLM Base URL"},
        "LLM_MODEL": {"value": "gpt-3.5-turbo", "desc": "LLM Model Name"}
    }

    for key, info in defaults.items():
        config = session.get(SystemConfig, key)
        if not config:
            session.add(SystemConfig(
                key=key,
                value=info["value"],
                description=info["desc"]
            ))
            session.commit()
