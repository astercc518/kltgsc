from sqlmodel import Session, select, text
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.system_config import SystemConfig
from app.models.warmup_template import WarmupTemplate

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
    else:
        # Sync password from .env on every startup
        from app.core.security import verify_password
        if not verify_password(settings.ADMIN_PASSWORD, user.hashed_password):
            user.hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
            session.add(user)
            session.commit()

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

    # --- 初始化默认养号模板 ---
    _init_warmup_templates(session)


def _init_warmup_templates(session: Session) -> None:
    existing = session.exec(select(WarmupTemplate).limit(1)).first()
    if existing:
        return  # 已有模板，跳过

    # 安全的公共频道列表（Telegram 官方 & 知名新闻频道）
    safe_channels = "telegram,durov,contest,designers,bloomberg,bbcnews,nytimes,techcrunch,androidchannel,nasa"
    crypto_channels = "cabormarket,WuBlockchain,crypto,coindesk_channel,cointelegraph,OKX_Announcements,gate_io,Bybit_Official"
    mixed_channels = "telegram,durov,bloomberg,bbcnews,cabormarket,WuBlockchain,techcrunch"

    templates = [
        WarmupTemplate(
            name="新号轻度养号（推荐首日）",
            description="新注册账号首日使用。低频浏览官方频道，模拟新用户行为，避免触发风控。",
            action_type="view_channel",
            min_delay=30,
            max_delay=90,
            duration_minutes=15,
            target_channels=safe_channels,
            is_default=True,
        ),
        WarmupTemplate(
            name="日常浏览养号",
            description="每日常规养号。混合浏览+点赞，保持账号活跃度，适合所有非新号账号。",
            action_type="mixed",
            min_delay=10,
            max_delay=45,
            duration_minutes=30,
            target_channels=safe_channels,
        ),
        WarmupTemplate(
            name="深度互动养号",
            description="高强度养号。大量浏览和点赞，适合准备投入营销前的深度预热（建议养号3天以上再用）。",
            action_type="mixed",
            min_delay=5,
            max_delay=20,
            duration_minutes=60,
            target_channels=mixed_channels,
        ),
        WarmupTemplate(
            name="Crypto 行业养号",
            description="针对加密货币行业的养号模板。浏览 Crypto 相关频道，让账号建立行业画像。",
            action_type="mixed",
            min_delay=10,
            max_delay=40,
            duration_minutes=30,
            target_channels=crypto_channels,
        ),
        WarmupTemplate(
            name="低频维持活跃",
            description="已完成深度养号的账号维持活跃用。每天跑一次，最低频率保持在线状态。",
            action_type="view_channel",
            min_delay=60,
            max_delay=180,
            duration_minutes=20,
            target_channels=safe_channels,
        ),
    ]

    for t in templates:
        session.add(t)
    session.commit()
