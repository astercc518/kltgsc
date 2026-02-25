from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class AIConfig(SQLModel, table=True):
    """AI配置模型，支持存储多个AI服务配置"""
    __tablename__ = "ai_config"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # 配置名称，如 "GPT-4o 主力"
    provider: str  # openai, gemini, deepseek, anthropic, qwen, moonshot, zhipu, doubao, openrouter, custom
    api_key: str  # API Key (加密存储)
    base_url: str = ""  # API Base URL，Gemini不需要
    model: str  # 模型名称
    is_default: bool = Field(default=False, index=True)  # 是否为默认配置
    is_active: bool = Field(default=True)  # 是否启用
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AIConfigCreate(SQLModel):
    """创建AI配置的请求模型"""
    name: str
    provider: str
    api_key: str
    base_url: str = ""
    model: str
    is_default: bool = False


class AIConfigUpdate(SQLModel):
    """更新AI配置的请求模型"""
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class AIConfigResponse(SQLModel):
    """AI配置响应模型（隐藏API Key）"""
    id: int
    name: str
    provider: str
    base_url: str
    model: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # 不返回完整的 api_key，只返回是否已配置
    has_api_key: bool = True
