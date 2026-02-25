"""
自动化工作流引擎

支持以下自动化流程：
1. 采集 → AI评分 → 分层触达
2. 新成员 → 截流 → 私聊
3. 私聊回复 → AI跟进 → 转化
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from sqlmodel import Session, select

from app.models.account import Account
from app.models.target_user import TargetUser
from app.models.campaign import Campaign
from app.services.ai_engine import AIEngine

logger = logging.getLogger(__name__)


class WorkflowType(str, Enum):
    SCRAPE_AND_REACH = "scrape_and_reach"  # 采集触达流程
    INTERCEPT_DM = "intercept_dm"  # 截流私聊流程
    AUTO_REPLY = "auto_reply"  # 自动回复流程


class ActionType(str, Enum):
    SCRAPE = "scrape"
    AI_SCORE = "ai_score"
    FILTER = "filter"
    SEND_DM = "send_dm"
    INVITE_GROUP = "invite_group"
    AI_REPLY = "ai_reply"
    WAIT = "wait"
    NOTIFY = "notify"


@dataclass
class WorkflowAction:
    """工作流动作"""
    action_type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None  # 条件表达式
    next_action_on_success: Optional[str] = None
    next_action_on_failure: Optional[str] = None


@dataclass
class WorkflowConfig:
    """工作流配置"""
    workflow_type: WorkflowType
    name: str
    campaign_id: Optional[int] = None
    actions: List[WorkflowAction] = field(default_factory=list)
    is_active: bool = True


# 战斗角色权限配置
COMBAT_ROLE_PERMISSIONS = {
    "cannon": {
        "allowed_actions": [
            ActionType.SEND_DM,
            ActionType.INVITE_GROUP,
        ],
        "daily_limit": 100,
        "min_delay_seconds": 30,
        "max_delay_seconds": 60,
        "description": "炮灰组：高风险批量操作"
    },
    "scout": {
        "allowed_actions": [
            ActionType.SCRAPE,
        ],
        "daily_limit": 0,  # 不限制采集
        "min_delay_seconds": 0,
        "max_delay_seconds": 0,
        "description": "侦察组：只读操作，禁止发消息"
    },
    "actor": {
        "allowed_actions": [
            ActionType.SEND_DM,
            ActionType.AI_REPLY,
        ],
        "daily_limit": 50,
        "min_delay_seconds": 120,
        "max_delay_seconds": 300,
        "require_script": True,
        "description": "演员组：炒群对话，需使用剧本"
    },
    "sniper": {
        "allowed_actions": [
            ActionType.SEND_DM,
            ActionType.AI_REPLY,
        ],
        "daily_limit": 20,
        "min_delay_seconds": 300,
        "max_delay_seconds": 600,
        "require_high_value_target": True,
        "min_target_score": 70,
        "description": "狙击组：精准打击高价值目标"
    }
}


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, session: Session):
        self.session = session
        self.ai_engine = AIEngine(session)
    
    def check_account_permission(
        self,
        account: Account,
        action_type: ActionType
    ) -> Dict[str, Any]:
        """
        检查账号是否有权限执行指定操作
        
        Returns:
            {"allowed": bool, "reason": str, "limits": dict}
        """
        combat_role = account.combat_role or "cannon"
        role_config = COMBAT_ROLE_PERMISSIONS.get(combat_role, COMBAT_ROLE_PERMISSIONS["cannon"])
        
        # 检查操作是否允许
        if action_type not in role_config["allowed_actions"]:
            return {
                "allowed": False,
                "reason": f"角色 {combat_role} 不允许执行 {action_type.value} 操作",
                "role": combat_role
            }
        
        # 检查每日限制
        daily_limit = role_config.get("daily_limit", 100)
        if daily_limit > 0 and account.daily_action_count >= daily_limit:
            return {
                "allowed": False,
                "reason": f"已达到每日操作限制 ({daily_limit})",
                "role": combat_role,
                "daily_count": account.daily_action_count,
                "daily_limit": daily_limit
            }
        
        return {
            "allowed": True,
            "role": combat_role,
            "limits": {
                "daily_limit": daily_limit,
                "daily_used": account.daily_action_count,
                "min_delay": role_config.get("min_delay_seconds", 30),
                "max_delay": role_config.get("max_delay_seconds", 60)
            }
        }
    
    def select_account_for_action(
        self,
        action_type: ActionType,
        target_score: Optional[int] = None,
        exclude_ids: List[int] = None
    ) -> Optional[Account]:
        """
        为指定操作选择合适的账号
        
        基于战斗角色和目标分数智能选择
        """
        exclude_ids = exclude_ids or []
        
        # 确定需要的角色
        if action_type == ActionType.SCRAPE:
            preferred_roles = ["scout", "cannon"]
        elif target_score and target_score >= 70:
            preferred_roles = ["sniper", "actor"]
        else:
            preferred_roles = ["cannon", "actor"]
        
        for role in preferred_roles:
            accounts = self.session.exec(
                select(Account).where(
                    Account.status == "active",
                    Account.combat_role == role,
                    Account.id.notin_(exclude_ids)
                ).order_by(Account.health_score.desc())
            ).all()
            
            for account in accounts:
                perm = self.check_account_permission(account, action_type)
                if perm["allowed"]:
                    return account
        
        return None
    
    def increment_account_action_count(self, account: Account):
        """增加账号的操作计数"""
        account.daily_action_count = (account.daily_action_count or 0) + 1
        self.session.add(account)
        self.session.commit()
    
    async def execute_scrape_and_reach_workflow(
        self,
        source_group_id: int,
        campaign_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行采集触达工作流
        
        步骤:
        1. 使用Scout账号采集目标用户
        2. AI评分并分层
        3. 高分用户使用Sniper私聊
        4. 中分用户使用Cannon拉群
        """
        from app.models.source_group import SourceGroup
        
        result = {
            "workflow": "scrape_and_reach",
            "source_group_id": source_group_id,
            "steps": []
        }
        
        # 步骤1: 获取流量源
        source_group = self.session.get(SourceGroup, source_group_id)
        if not source_group:
            result["error"] = "Source group not found"
            return result
        
        result["steps"].append({
            "step": 1,
            "action": "get_source_group",
            "result": {"name": source_group.name, "link": source_group.link}
        })
        
        # 步骤2: 选择Scout账号进行采集
        scout = self.select_account_for_action(ActionType.SCRAPE)
        if not scout:
            result["error"] = "No available scout account"
            return result
        
        result["steps"].append({
            "step": 2,
            "action": "select_scout",
            "result": {"account_id": scout.id, "phone": scout.phone_number}
        })
        
        # 步骤3: 获取待处理的高分用户
        high_value_users = self.session.exec(
            select(TargetUser).where(
                TargetUser.source_group == source_group.link,
                TargetUser.ai_score >= 70,
                TargetUser.funnel_stage == "raw"
            ).limit(10)
        ).all()
        
        result["steps"].append({
            "step": 3,
            "action": "find_high_value_users",
            "result": {"count": len(high_value_users)}
        })
        
        # 步骤4: 为高分用户选择Sniper
        if high_value_users:
            sniper = self.select_account_for_action(
                ActionType.SEND_DM,
                target_score=80
            )
            if sniper:
                result["steps"].append({
                    "step": 4,
                    "action": "select_sniper",
                    "result": {
                        "account_id": sniper.id,
                        "targets": [u.username for u in high_value_users]
                    }
                })
        
        return result
    
    def get_role_stats(self) -> Dict[str, Any]:
        """获取各角色统计"""
        stats = {}
        for role in COMBAT_ROLE_PERMISSIONS.keys():
            total = self.session.exec(
                select(Account).where(Account.combat_role == role)
            ).all()
            active = [a for a in total if a.status == "active"]
            available = [a for a in active if (a.daily_action_count or 0) < COMBAT_ROLE_PERMISSIONS[role].get("daily_limit", 100)]
            
            stats[role] = {
                "total": len(total),
                "active": len(active),
                "available": len(available),
                "config": COMBAT_ROLE_PERMISSIONS[role]
            }
        
        return stats
