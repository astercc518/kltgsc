#!/usr/bin/env python3
"""
迁移脚本：将旧的 SystemConfig 中的 LLM 配置迁移到新的 AIConfig 表
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select, SQLModel
from app.core.db import engine
from app.models.system_config import SystemConfig
from app.models.ai_config import AIConfig
from datetime import datetime


def migrate():
    """迁移旧的 LLM 配置到 AIConfig 表"""
    
    # 创建表（如果不存在）
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 检查是否已经有 AIConfig 数据
        existing = session.exec(select(AIConfig)).first()
        if existing:
            print("AIConfig 表中已有数据，跳过迁移")
            return
        
        # 读取旧的配置
        def get_config(key: str) -> str:
            config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
            return config.value if config else ""
        
        api_key = get_config("llm_api_key")
        provider = get_config("llm_provider") or "openai"
        model = get_config("llm_model") or "gpt-3.5-turbo"
        base_url = get_config("llm_base_url") or ""
        
        if not api_key:
            print("旧配置中没有 API Key，跳过迁移")
            return
        
        # 创建新的 AIConfig 记录
        ai_config = AIConfig(
            name=f"默认 {provider.upper()} 配置",
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            is_default=True,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(ai_config)
        session.commit()
        
        print(f"成功迁移配置: {ai_config.name}")
        print(f"  Provider: {provider}")
        print(f"  Model: {model}")
        print(f"  Base URL: {base_url or '(默认)'}")


if __name__ == "__main__":
    migrate()
