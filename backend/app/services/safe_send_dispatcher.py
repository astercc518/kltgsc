"""
安全发送调度器
实现智能账号分配、发送限制、休息机制
"""
import random
import asyncio
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime, date, timedelta
from dataclasses import dataclass

from sqlmodel import Session, select, func
from app.models.account import Account
from app.models.account_stats import AccountSendStats
from app.models.target_user import TargetUser

logger = logging.getLogger(__name__)


@dataclass
class SafeSendConfig:
    """安全发送配置"""
    # === 每账号限制 ===
    max_daily_sends_new: int = 15  # 新账号（<7天）每日最大发送
    max_daily_sends_normal: int = 30  # 普通账号每日最大发送
    max_daily_sends_trusted: int = 50  # 信任账号（>30天）每日最大发送
    
    # === 发送间隔 ===
    min_delay_seconds: int = 60  # 最小间隔（秒）
    max_delay_seconds: int = 180  # 最大间隔（秒）
    
    # === 休息机制 ===
    sends_before_rest: int = 5  # 连续发送多少条后休息
    rest_duration_min: int = 300  # 最短休息时间（秒）= 5分钟
    rest_duration_max: int = 900  # 最长休息时间（秒）= 15分钟
    
    # === 风险控制 ===
    max_flood_wait_daily: int = 2  # 每日触发 FloodWait 次数上限，超过则停用
    max_errors_daily: int = 5  # 每日错误次数上限
    cooldown_after_flood: int = 3600  # 触发 FloodWait 后冷却时间（秒）= 1小时
    
    # === 批次控制 ===
    max_targets_per_batch: int = 500  # 每批最大目标数
    batch_interval_hours: int = 4  # 批次间隔（小时）
    
    @classmethod
    def load_from_db(cls, session) -> 'SafeSendConfig':
        """从数据库加载配置"""
        from app.models.system_config import SystemConfig
        
        config = cls()
        fields = [
            'max_daily_sends_new', 'max_daily_sends_normal', 'max_daily_sends_trusted',
            'min_delay_seconds', 'max_delay_seconds', 'sends_before_rest',
            'rest_duration_min', 'rest_duration_max', 'max_flood_wait_daily',
            'cooldown_after_flood'
        ]
        
        for field in fields:
            config_key = f"safe_send_{field}"
            db_config = session.exec(
                select(SystemConfig).where(SystemConfig.key == config_key)
            ).first()
            if db_config:
                setattr(config, field, int(db_config.value))
        
        return config


class SafeSendDispatcher:
    """安全发送调度器"""
    
    def __init__(self, session: Session, config: Optional[SafeSendConfig] = None):
        self.session = session
        self.config = config or SafeSendConfig()
        
    def get_account_daily_limit(self, account: Account) -> int:
        """根据账号年龄获取每日发送限制"""
        if not account.created_at:
            return self.config.max_daily_sends_normal
            
        account_age_days = (datetime.utcnow() - account.created_at).days
        
        if account_age_days < 7:
            return self.config.max_daily_sends_new
        elif account_age_days > 30:
            return self.config.max_daily_sends_trusted
        else:
            return self.config.max_daily_sends_normal
    
    def get_or_create_stats(self, account_id: int, stat_date: date = None) -> AccountSendStats:
        """获取或创建账号今日统计"""
        if stat_date is None:
            stat_date = date.today()
            
        stats = self.session.exec(
            select(AccountSendStats).where(
                AccountSendStats.account_id == account_id,
                AccountSendStats.stat_date == stat_date
            )
        ).first()
        
        if not stats:
            stats = AccountSendStats(
                account_id=account_id,
                stat_date=stat_date
            )
            self.session.add(stats)
            self.session.commit()
            self.session.refresh(stats)
            
        return stats
    
    def get_available_accounts(self, account_ids: List[int]) -> List[Tuple[Account, int]]:
        """
        获取可用账号列表，按剩余配额排序
        返回: [(account, remaining_quota), ...]
        """
        today = date.today()
        available = []
        
        for acc_id in account_ids:
            account = self.session.get(Account, acc_id)
            if not account:
                continue
                
            # 检查账号状态
            if account.status != 'active':
                continue
                
            # 检查冷却时间
            if account.cooldown_until and account.cooldown_until > datetime.utcnow():
                continue
            
            # 获取今日统计
            stats = self.get_or_create_stats(acc_id, today)
            
            # 检查风险
            if stats.flood_wait_count >= self.config.max_flood_wait_daily:
                logger.warning(f"Account {acc_id} exceeded daily FloodWait limit")
                continue
                
            if stats.error_count >= self.config.max_errors_daily:
                logger.warning(f"Account {acc_id} exceeded daily error limit")
                continue
            
            # 计算剩余配额
            daily_limit = self.get_account_daily_limit(account)
            remaining = daily_limit - stats.send_count
            
            if remaining > 0:
                available.append((account, remaining, stats))
        
        # 按剩余配额降序排序（优先使用配额多的账号）
        available.sort(key=lambda x: x[1], reverse=True)
        
        return available
    
    def calculate_total_capacity(self, account_ids: List[int]) -> int:
        """计算所有账号今日剩余总容量"""
        available = self.get_available_accounts(account_ids)
        return sum(remaining for _, remaining, _ in available)
    
    def should_rest(self, stats: AccountSendStats) -> Tuple[bool, int]:
        """
        判断是否需要休息
        返回: (需要休息, 休息时长秒)
        """
        if stats.consecutive_sends >= self.config.sends_before_rest:
            rest_duration = random.randint(
                self.config.rest_duration_min,
                self.config.rest_duration_max
            )
            return True, rest_duration
        return False, 0
    
    def get_send_delay(self) -> int:
        """获取发送间隔（随机）"""
        return random.randint(
            self.config.min_delay_seconds,
            self.config.max_delay_seconds
        )
    
    def select_next_account(self, available_accounts: List[Tuple[Account, int, AccountSendStats]]) -> Optional[Tuple[Account, AccountSendStats]]:
        """
        选择下一个发送账号
        策略：加权随机选择，配额多的账号被选中概率更高
        """
        if not available_accounts:
            return None
            
        # 过滤掉配额为0的
        valid = [(acc, remaining, stats) for acc, remaining, stats in available_accounts if remaining > 0]
        if not valid:
            return None
        
        # 加权随机选择
        total_weight = sum(remaining for _, remaining, _ in valid)
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for acc, remaining, stats in valid:
            cumulative += remaining
            if r <= cumulative:
                return acc, stats
        
        # 默认返回第一个
        return valid[0][0], valid[0][2]
    
    def record_send(self, account_id: int, success: bool, error_type: str = None):
        """记录一次发送"""
        stats = self.get_or_create_stats(account_id)
        
        stats.send_count += 1
        stats.consecutive_sends += 1
        stats.last_send_at = datetime.utcnow()
        
        if stats.first_send_at is None:
            stats.first_send_at = datetime.utcnow()
        
        if success:
            stats.success_count += 1
        else:
            stats.fail_count += 1
            stats.error_count += 1
            
            # 处理 FloodWait
            if error_type and 'flood' in error_type.lower():
                stats.flood_wait_count += 1
                # 设置账号冷却
                account = self.session.get(Account, account_id)
                if account:
                    account.cooldown_until = datetime.utcnow() + timedelta(
                        seconds=self.config.cooldown_after_flood
                    )
                    self.session.add(account)
        
        self.session.add(stats)
        self.session.commit()
    
    def record_rest(self, account_id: int):
        """记录休息"""
        stats = self.get_or_create_stats(account_id)
        stats.consecutive_sends = 0
        stats.last_rest_at = datetime.utcnow()
        self.session.add(stats)
        self.session.commit()
    
    def create_send_plan(
        self, 
        account_ids: List[int], 
        target_user_ids: List[int]
    ) -> Dict:
        """
        创建发送计划
        返回发送计划，包括预计完成时间、分批信息等
        """
        total_targets = len(target_user_ids)
        total_capacity = self.calculate_total_capacity(account_ids)

        # 无可用账号或无目标时直接返回空计划
        if total_capacity <= 0:
            return {
                "total_targets": total_targets,
                "total_capacity_today": 0,
                "can_complete_today": False,
                "batches_needed": 0,
                "sends_today": 0,
                "sends_remaining": total_targets,
                "estimated_hours_today": 0,
            }

        # 计算需要多少批次/天
        if total_capacity >= total_targets:
            batches_needed = 1
            can_complete_today = True
        else:
            batches_needed = (total_targets + total_capacity - 1) // total_capacity
            can_complete_today = False
        
        # 计算预计完成时间
        avg_delay = (self.config.min_delay_seconds + self.config.max_delay_seconds) / 2
        rest_overhead = (self.config.rest_duration_min + self.config.rest_duration_max) / 2 / self.config.sends_before_rest
        time_per_message = avg_delay + rest_overhead
        
        today_sends = min(total_targets, total_capacity)
        estimated_hours_today = (today_sends * time_per_message) / 3600
        
        return {
            "total_targets": total_targets,
            "total_capacity_today": total_capacity,
            "can_complete_today": can_complete_today,
            "batches_needed": batches_needed,
            "sends_today": today_sends,
            "sends_remaining": max(0, total_targets - total_capacity),
            "estimated_hours_today": round(estimated_hours_today, 1),
            "estimated_days_total": batches_needed,
            "accounts_available": len(self.get_available_accounts(account_ids)),
            "avg_per_account": round(today_sends / len(account_ids), 1) if account_ids else 0
        }
    
    def get_account_stats_summary(self, account_ids: List[int]) -> List[Dict]:
        """获取账号统计摘要"""
        today = date.today()
        summary = []
        
        for acc_id in account_ids:
            account = self.session.get(Account, acc_id)
            if not account:
                continue
                
            stats = self.get_or_create_stats(acc_id, today)
            daily_limit = self.get_account_daily_limit(account)
            
            summary.append({
                "account_id": acc_id,
                "phone": account.phone_number,
                "status": account.status,
                "daily_limit": daily_limit,
                "sent_today": stats.send_count,
                "remaining": max(0, daily_limit - stats.send_count),
                "success_rate": round(stats.success_count / stats.send_count * 100, 1) if stats.send_count > 0 else 100,
                "flood_wait_count": stats.flood_wait_count,
                "is_available": account.status == 'active' and (daily_limit - stats.send_count) > 0
            })
        
        return summary
