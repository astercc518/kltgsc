"""
用户评分服务
基于用户行为和关键词命中进行评分，实现精准营销
"""
import logging
import json
from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import Session, select
from app.models.target_user import TargetUser

logger = logging.getLogger(__name__)


class ScoreService:
    def __init__(self, session: Session):
        self.session = session
    
    def calculate_keyword_score(self, message: str, intent_data: Optional[Dict] = None, base_weight: int = 10) -> int:
        """
        计算关键词命中的评分
        
        Args:
            message: 用户消息内容
            intent_data: AI 意图分析结果 (可选)
            base_weight: 关键词的基础权重
        
        Returns:
            int: 评分增量
        """
        score = base_weight
        
        # 1. 基于 AI 意图分析评分 (如果有)
        if intent_data:
            intent = intent_data.get("intent", "")
            if intent == "purchase":
                score += 20  # 明确购买意向
            elif intent == "inquiry":
                score += 10  # 询问产品
            elif intent == "competitor":
                score += 15  # 提及竞品 (潜在转化机会)
            
            if intent_data.get("is_high_value"):
                score += 10
        
        # 2. 基于内容关键词加分
        high_value_keywords = [
            "price", "cost", "buy", "purchase", "order",
            "多少钱", "价格", "购买", "下单", "怎么买", "代理", "加盟"
        ]
        for kw in high_value_keywords:
            if kw.lower() in message.lower():
                score += 5
                break  # 只加一次
        
        return score
    
    def update_user_score(
        self,
        telegram_id: int,
        score_delta: int,
        keyword: Optional[str] = None,
        tags: Optional[List[str]] = None,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        source_group: Optional[str] = None
    ) -> Optional[TargetUser]:
        """
        更新用户评分，并自动流转营销阶段
        
        Args:
            telegram_id: Telegram 用户 ID
            score_delta: 评分增量
            keyword: 命中的关键词
            tags: 要添加的标签
            username: 用户名 (用于创建新用户)
            first_name: 名字 (用于创建新用户)
            source_group: 来源群组
        
        Returns:
            TargetUser: 更新后的用户对象
        """
        # 查找或创建用户
        user = self.session.exec(
            select(TargetUser).where(TargetUser.telegram_id == telegram_id)
        ).first()
        
        if not user:
            # 创建新用户
            user = TargetUser(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                source_group=source_group,
                engagement_score=0,
                marketing_stage="new"
            )
            self.session.add(user)
            logger.info(f"Created new target user: {telegram_id}")
        
        # 更新评分
        user.engagement_score += score_delta
        
        # 更新关键词命中记录
        if keyword:
            user.last_hit_keyword = keyword
            user.last_hit_at = datetime.utcnow()
        
        # 合并标签
        if tags:
            existing_tags = []
            if user.tags:
                try:
                    existing_tags = json.loads(user.tags)
                except:
                    pass
            new_tags = list(set(existing_tags + tags))
            user.tags = json.dumps(new_tags)
        
        # 自动流转营销阶段
        self._update_marketing_stage(user)
        
        self.session.add(user)
        self.session.commit()
        
        logger.info(f"Updated user {telegram_id} score: +{score_delta}, total: {user.engagement_score}, stage: {user.marketing_stage}")
        
        return user
    
    def _update_marketing_stage(self, user: TargetUser):
        """
        根据评分自动流转营销阶段
        
        阶段定义:
        - new: 新用户 (0-9分)
        - warm: 已预热 (10-29分)
        - qualified: 高意向 (30-49分)
        - converted: 已转化 (50+分 或手动标记)
        - lost: 已流失 (手动标记)
        """
        if user.marketing_stage in ["converted", "lost"]:
            # 已终态，不自动流转
            return
        
        score = user.engagement_score
        
        if score >= 50:
            user.marketing_stage = "qualified"  # 不自动标记 converted，需要人工确认
        elif score >= 30:
            user.marketing_stage = "qualified"
        elif score >= 10:
            user.marketing_stage = "warm"
        else:
            user.marketing_stage = "new"
    
    def get_high_value_users(self, min_score: int = 30, limit: int = 50) -> List[TargetUser]:
        """
        获取高价值用户列表
        """
        users = self.session.exec(
            select(TargetUser)
            .where(TargetUser.engagement_score >= min_score)
            .where(TargetUser.marketing_stage.notin_(["converted", "lost"]))
            .order_by(TargetUser.engagement_score.desc())
            .limit(limit)
        ).all()
        return list(users)
