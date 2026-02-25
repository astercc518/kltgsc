"""
竞品群实时截流服务

功能：
1. 监控竞品群的新成员加入事件
2. 即时获取用户信息并进行AI评估
3. 高分用户自动触发私聊任务
"""
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from sqlmodel import Session, select

from app.models.source_group import SourceGroup
from app.models.target_user import TargetUser
from app.models.account import Account
from app.services.ai_engine import AIEngine

logger = logging.getLogger(__name__)


@dataclass
class InterceptConfig:
    """截流配置"""
    min_score_for_dm: int = 70  # 触发私聊的最低分数
    delay_before_dm_seconds: int = 300  # 截流后等待时间（5分钟）
    max_dm_per_hour: int = 10  # 每小时最大私聊数
    use_sniper_only: bool = True  # 是否仅使用狙击组账号
    enable_ai_opener: bool = True  # 是否使用AI生成开场白


class InterceptService:
    """竞品截流服务"""
    
    def __init__(self, session: Session):
        self.session = session
        self.config = InterceptConfig()
        self.ai_engine = AIEngine(session)
        self._dm_count_this_hour = 0
        self._last_hour_reset = datetime.utcnow().hour
    
    def _reset_hourly_counter(self):
        """重置小时计数器"""
        current_hour = datetime.utcnow().hour
        if current_hour != self._last_hour_reset:
            self._dm_count_this_hour = 0
            self._last_hour_reset = current_hour
    
    async def process_new_member(
        self,
        source_group_id: int,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        bio: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理新成员加入事件
        
        Args:
            source_group_id: 流量源ID
            user_id: Telegram用户ID
            username: 用户名
            first_name: 名字
            bio: 简介
            
        Returns:
            处理结果
        """
        self._reset_hourly_counter()
        
        # 获取流量源信息
        source_group = self.session.get(SourceGroup, source_group_id)
        if not source_group:
            return {"status": "error", "message": "Source group not found"}
        
        # 检查是否是竞品群
        if source_group.type != "competitor":
            return {"status": "skipped", "message": "Not a competitor group"}
        
        # 检查用户是否已存在
        existing = self.session.exec(
            select(TargetUser).where(TargetUser.telegram_id == user_id)
        ).first()
        
        if existing:
            return {"status": "skipped", "message": "User already exists", "user_id": user_id}
        
        # AI评估用户
        analysis = await self.ai_engine.analyze_user(
            username=username or str(user_id),
            bio=bio,
            messages=None
        )
        
        # 保存用户
        target_user = TargetUser(
            telegram_id=user_id,
            username=username,
            first_name=first_name,
            bio=bio,
            source_group=source_group.link,
            ai_score=analysis.score,
            ai_tags=str(analysis.tags),
            ai_summary=analysis.summary,
            funnel_stage="raw"
        )
        self.session.add(target_user)
        
        # 更新流量源统计
        source_group.total_scraped += 1
        if analysis.score >= 70:
            source_group.high_value_count += 1
        self.session.add(source_group)
        
        self.session.commit()
        self.session.refresh(target_user)
        
        result = {
            "status": "captured",
            "user_id": user_id,
            "username": username,
            "ai_score": analysis.score,
            "ai_summary": analysis.summary,
            "source_group": source_group.name or source_group.link
        }
        
        # 检查是否应该触发私聊
        if analysis.score >= self.config.min_score_for_dm:
            if self._dm_count_this_hour < self.config.max_dm_per_hour:
                result["dm_scheduled"] = True
                result["dm_delay_seconds"] = self.config.delay_before_dm_seconds
                self._dm_count_this_hour += 1
                
                # 更新用户状态
                target_user.funnel_stage = "qualified"
                self.session.add(target_user)
                self.session.commit()
            else:
                result["dm_scheduled"] = False
                result["dm_reason"] = "Hourly limit reached"
        else:
            result["dm_scheduled"] = False
            result["dm_reason"] = f"Score {analysis.score} below threshold {self.config.min_score_for_dm}"
        
        logger.info(f"Intercepted new member: {username or user_id}, score: {analysis.score}")
        return result
    
    async def get_sniper_account(self) -> Optional[Account]:
        """获取可用的狙击账号"""
        query = select(Account).where(
            Account.status == "active",
            Account.combat_role == "sniper"
        )
        
        accounts = self.session.exec(query).all()
        if not accounts:
            # 降级到演员组
            query = select(Account).where(
                Account.status == "active",
                Account.combat_role == "actor"
            )
            accounts = self.session.exec(query).all()
        
        if not accounts:
            return None
        
        # 选择健康分最高的账号
        return max(accounts, key=lambda a: a.health_score or 0)
    
    async def generate_dm_content(
        self,
        target_user: TargetUser,
        persona_id: Optional[int] = None
    ) -> str:
        """为目标用户生成私聊内容"""
        if not self.config.enable_ai_opener:
            return "你好！看到你刚加入群，想认识一下 👋"
        
        user_summary = target_user.ai_summary or f"用户名: {target_user.username}"
        opener = await self.ai_engine.generate_opener(
            user_summary=user_summary,
            persona_id=persona_id,
            tone="friendly"
        )
        return opener
    
    def get_intercept_stats(self) -> Dict[str, Any]:
        """获取截流统计"""
        # 获取所有竞品群
        competitor_groups = self.session.exec(
            select(SourceGroup).where(SourceGroup.type == "competitor")
        ).all()
        
        # 今日截获数
        today = datetime.utcnow().date()
        today_captures = self.session.exec(
            select(TargetUser).where(
                TargetUser.created_at >= datetime.combine(today, datetime.min.time())
            )
        ).all()
        
        # 高分用户
        high_value_today = [u for u in today_captures if (u.ai_score or 0) >= 70]
        
        return {
            "competitor_groups": len(competitor_groups),
            "today_captures": len(today_captures),
            "today_high_value": len(high_value_today),
            "dm_count_this_hour": self._dm_count_this_hour,
            "dm_limit_per_hour": self.config.max_dm_per_hour
        }


# Celery 任务
def create_intercept_dm_task(user_id: int, delay_seconds: int = 300):
    """创建延迟私聊任务"""
    from app.core.celery_app import celery_app
    
    celery_app.send_task(
        "app.tasks.marketing_tasks.send_intercept_dm",
        args=[user_id],
        countdown=delay_seconds
    )
