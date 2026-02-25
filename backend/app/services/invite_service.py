"""
增强版邀请服务 - 批量拉人核心逻辑
功能：
1. 账号池管理与每日限额
2. 智能错误处理与冷却机制
3. 详细日志记录
4. 高级目标筛选
"""
import logging
import asyncio
import random
import json
import re
from typing import List, Optional, Dict, Tuple, Any
from sqlmodel import Session, select, func, and_, or_
from sqlalchemy import text
from datetime import datetime, timedelta
import time

from app.models.account import Account
from app.models.target_user import TargetUser
from app.models.invite_task import InviteTask
from app.models.invite_log import InviteLog, InviteLogCreate, InviteStats, AccountInviteStats
from app.services.telegram_client import _create_client_and_run

logger = logging.getLogger(__name__)


# === 错误代码映射 ===
ERROR_CODE_MAP = {
    "USER_PRIVACY_RESTRICTED": "privacy_restricted",
    "PRIVACY_RESTRICTED": "privacy_restricted",
    "USER_BANNED_IN_CHANNEL": "banned",
    "USER_NOT_MUTUAL_CONTACT": "not_mutual",
    "PEER_FLOOD": "peer_flood",
    "FLOOD_WAIT": "peer_flood",
    "CHAT_WRITE_FORBIDDEN": "chat_forbidden",
    "USER_NOT_PARTICIPANT": "not_participant",
    "INVITE_HASH_EXPIRED": "invite_expired",
    "USER_ALREADY_PARTICIPANT": "already_member",
    "USERS_TOO_MUCH": "users_too_much",
    "USER_CHANNELS_TOO_MUCH": "channels_too_much",
}


def parse_error_code(error_str: str) -> Tuple[str, Optional[int]]:
    """解析错误字符串，返回错误代码和可能的等待时间"""
    error_upper = error_str.upper()
    
    # 检查 FloodWait 并提取等待时间
    flood_match = re.search(r'FLOOD_WAIT[_\s]*(\d+)', error_upper)
    if flood_match:
        wait_seconds = int(flood_match.group(1))
        return "peer_flood", wait_seconds
    
    # 匹配已知错误代码
    for key, code in ERROR_CODE_MAP.items():
        if key in error_upper:
            return code, None
    
    return "other_error", None


class InviteService:
    """增强版邀请服务"""
    
    def __init__(self, session: Session):
        self.session = session
    
    # ==================== 账号池管理 ====================
    
    def get_available_accounts(
        self, 
        account_ids: Optional[List[int]] = None,
        account_group: Optional[str] = None,
        daily_limit: int = 20,
        exclude_cooling: bool = True
    ) -> List[Account]:
        """
        获取可用于拉人的账号列表
        
        Args:
            account_ids: 指定账号ID列表
            account_group: 账号组名称（如 "invite_cannon"）
            daily_limit: 每日拉人限制
            exclude_cooling: 是否排除冷却中的账号
        
        Returns:
            可用账号列表，按今日已用次数升序排列
        """
        # 基础查询：活跃账号
        query = select(Account).where(
            Account.status == "active",
            Account.is_banned == False
        )
        
        # 按账号ID或账号组筛选
        if account_ids:
            query = query.where(Account.id.in_(account_ids))
        elif account_group:
            query = query.where(Account.combat_role == account_group)
        
        accounts = list(self.session.exec(query).all())
        
        # 获取每个账号的今日统计
        available = []
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for account in accounts:
            stats = self.get_account_invite_stats(account.id, today_start)
            
            # 检查每日限额
            if stats.today_count >= daily_limit:
                logger.debug(f"Account {account.id} reached daily limit ({stats.today_count}/{daily_limit})")
                continue
            
            # 检查冷却状态
            if exclude_cooling and stats.cooldown_until and stats.cooldown_until > datetime.utcnow():
                logger.debug(f"Account {account.id} is cooling down until {stats.cooldown_until}")
                continue
            
            # 附加统计信息
            account._invite_stats = stats
            available.append(account)
        
        # 按今日使用次数升序排列（优先使用用得少的账号）
        available.sort(key=lambda a: a._invite_stats.today_count)
        
        return available
    
    def get_account_invite_stats(self, account_id: int, since: Optional[datetime] = None) -> AccountInviteStats:
        """获取账号的邀请统计"""
        if since is None:
            since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # 今日统计 - use COUNT queries instead of loading all logs
        today_count = self.session.exec(
            select(func.count(InviteLog.id)).where(
                InviteLog.account_id == account_id,
                InviteLog.created_at >= since
            )
        ).one()

        today_success = self.session.exec(
            select(func.count(InviteLog.id)).where(
                InviteLog.account_id == account_id,
                InviteLog.created_at >= since,
                InviteLog.status == "success"
            )
        ).one()

        today_failed = today_count - today_success

        # 总统计
        total_count = self.session.exec(
            select(func.count(InviteLog.id)).where(InviteLog.account_id == account_id)
        ).one()

        total_success = self.session.exec(
            select(func.count(InviteLog.id)).where(
                InviteLog.account_id == account_id,
                InviteLog.status == "success"
            )
        ).one()

        # 最后邀请时间 - only fetch the timestamp, not the full row
        last_log = self.session.exec(
            select(InviteLog.created_at).where(InviteLog.account_id == account_id)
            .order_by(InviteLog.created_at.desc()).limit(1)
        ).first()

        # 最后风控时间和冷却状态
        last_flood = self.session.exec(
            select(InviteLog.created_at, InviteLog.flood_wait_seconds).where(
                InviteLog.account_id == account_id,
                InviteLog.error_code == "peer_flood"
            ).order_by(InviteLog.created_at.desc()).limit(1)
        ).first()

        cooldown_until = None
        last_flood_at = None
        if last_flood:
            last_flood_at = last_flood[0]
            flood_wait_seconds = last_flood[1]
            # 默认冷却24小时
            cooldown_hours = 24
            if flood_wait_seconds:
                # 如果有具体等待时间，使用它（加上缓冲）
                cooldown_hours = max(24, flood_wait_seconds / 3600 * 1.5)
            cooldown_until = last_flood_at + timedelta(hours=cooldown_hours)

        account = self.session.get(Account, account_id)

        return AccountInviteStats(
            account_id=account_id,
            account_username=account.username if account else None,
            today_count=today_count,
            today_success=today_success,
            today_failed=today_failed,
            total_count=total_count,
            total_success=total_success,
            last_invite_at=last_log if last_log else None,
            last_flood_at=last_flood_at,
            cooldown_until=cooldown_until,
            is_available=cooldown_until is None or cooldown_until <= datetime.utcnow()
        )
    
    # ==================== 目标用户筛选 ====================
    
    def filter_target_users(
        self,
        target_user_ids: Optional[List[int]] = None,
        filter_tags: Optional[List[str]] = None,
        filter_min_score: Optional[int] = None,
        filter_funnel_stages: Optional[List[str]] = None,
        filter_source_groups: Optional[List[str]] = None,
        exclude_invited: bool = True,
        exclude_failed_recently: bool = True,
        failed_cooldown_hours: int = 72,
        max_targets: int = 100
    ) -> List[TargetUser]:
        """
        高级目标用户筛选
        
        Args:
            target_user_ids: 直接指定的用户ID列表
            filter_tags: 筛选标签（任意匹配）
            filter_min_score: 最低AI评分
            filter_funnel_stages: 筛选漏斗阶段
            filter_source_groups: 筛选来源群
            exclude_invited: 排除已成功邀请的用户
            exclude_failed_recently: 排除近期失败的用户
            failed_cooldown_hours: 失败冷却时间
            max_targets: 最大返回数量
        
        Returns:
            符合条件的目标用户列表
        """
        query = select(TargetUser)
        conditions = []
        
        # 直接指定ID
        if target_user_ids:
            conditions.append(TargetUser.id.in_(target_user_ids))
        
        # 标签筛选
        if filter_tags:
            tag_conditions = []
            for tag in filter_tags:
                tag_conditions.append(TargetUser.tags.contains(tag))
                tag_conditions.append(TargetUser.ai_tags.contains(tag))
            if tag_conditions:
                conditions.append(or_(*tag_conditions))
        
        # 评分筛选
        if filter_min_score is not None:
            conditions.append(TargetUser.ai_score >= filter_min_score)
        
        # 漏斗阶段筛选
        if filter_funnel_stages:
            conditions.append(TargetUser.funnel_stage.in_(filter_funnel_stages))
        
        # 来源群筛选
        if filter_source_groups:
            conditions.append(TargetUser.source_group.in_(filter_source_groups))
        
        # 排除已成功邀请
        if exclude_invited:
            conditions.append(TargetUser.invite_status != "success")
        
        # 排除近期失败
        if exclude_failed_recently:
            cooldown_threshold = datetime.utcnow() - timedelta(hours=failed_cooldown_hours)
            conditions.append(
                or_(
                    TargetUser.invite_attempted_at.is_(None),
                    TargetUser.invite_status == "untried",
                    and_(
                        TargetUser.invite_status != "success",
                        TargetUser.invite_attempted_at < cooldown_threshold
                    )
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # 优先级排序：高评分优先
        query = query.order_by(
            TargetUser.ai_score.desc().nullslast(),
            TargetUser.engagement_score.desc(),
            TargetUser.created_at.desc()
        ).limit(max_targets)
        
        return list(self.session.exec(query).all())
    
    # ==================== 核心邀请逻辑 ====================
    
    async def execute_invite_task(self, task_id: int) -> Dict[str, Any]:
        """
        执行邀请任务（由 Celery Worker 调用）
        
        Args:
            task_id: 任务ID
        
        Returns:
            执行结果统计
        """
        task = self.session.get(InviteTask, task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        # 更新任务状态
        task.status = "running"
        task.started_at = datetime.utcnow()
        self.session.add(task)
        self.session.commit()
        
        try:
            result = await self._execute_task_internal(task)
            
            # 更新任务最终状态
            if task.pending_count == 0:
                task.status = "completed"
            elif result.get("flood_stopped"):
                task.status = "paused"
                task.last_error = "Paused due to FloodWait"
            else:
                task.status = "completed"
            
            task.completed_at = datetime.utcnow()
            self.session.add(task)
            self.session.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task.status = "failed"
            task.last_error = str(e)[:500]
            self.session.add(task)
            self.session.commit()
            return {"success": False, "error": str(e)}
    
    async def _execute_task_internal(self, task: InviteTask) -> Dict[str, Any]:
        """内部执行逻辑"""
        # 解析配置
        account_ids = json.loads(task.account_ids_json) if task.account_ids_json else None
        target_user_ids = json.loads(task.target_user_ids_json) if task.target_user_ids_json else None
        filter_tags = json.loads(task.filter_tags) if task.filter_tags else None
        filter_funnel_stages = json.loads(task.filter_funnel_stages) if task.filter_funnel_stages else None
        
        # 获取可用账号
        accounts = self.get_available_accounts(
            account_ids=account_ids,
            account_group=task.account_group,
            daily_limit=task.max_invites_per_account
        )
        
        if not accounts:
            return {"success": False, "error": "No available accounts"}
        
        # 获取目标用户
        targets = self.filter_target_users(
            target_user_ids=target_user_ids,
            filter_tags=filter_tags,
            filter_min_score=task.filter_min_score,
            filter_funnel_stages=filter_funnel_stages,
            exclude_invited=task.exclude_invited,
            exclude_failed_recently=task.exclude_failed_recently,
            failed_cooldown_hours=task.failed_cooldown_hours,
            max_targets=task.max_invites_per_task
        )
        
        if not targets:
            return {"success": False, "error": "No valid targets after filtering"}
        
        # 更新任务统计
        task.total_count = len(targets)
        task.pending_count = len(targets)
        self.session.add(task)
        self.session.commit()
        
        # 分配任务给账号
        result = {
            "success": 0,
            "failed": 0,
            "privacy_restricted": 0,
            "peer_flood": 0,
            "flood_stopped": False,
            "errors": []
        }
        
        target_index = 0
        account_index = 0
        
        while target_index < len(targets):
            if task.status == "paused":
                break
            
            # 获取当前账号
            account = accounts[account_index % len(accounts)]
            
            # 检查账号是否还能用
            stats = self.get_account_invite_stats(account.id)
            if stats.today_count >= task.max_invites_per_account:
                account_index += 1
                if account_index >= len(accounts):
                    # 所有账号都用完了
                    logger.warning("All accounts reached daily limit")
                    break
                continue
            
            # 获取当前目标
            target = targets[target_index]
            target_index += 1
            
            # 执行单次邀请
            invite_result = await self._invite_single_user(
                task=task,
                account=account,
                target=target,
                channel_link=task.target_channel,
                min_delay=task.min_delay,
                max_delay=task.max_delay
            )
            
            # 更新统计
            if invite_result["status"] == "success":
                result["success"] += 1
                task.success_count += 1
            else:
                result["failed"] += 1
                task.fail_count += 1
                
                if invite_result["error_code"] == "privacy_restricted":
                    result["privacy_restricted"] += 1
                    task.privacy_restricted_count += 1
                elif invite_result["error_code"] == "peer_flood":
                    result["peer_flood"] += 1
                    task.flood_wait_count += 1
                    
                    if task.stop_on_flood:
                        result["flood_stopped"] = True
                        logger.warning(f"Task {task.id} stopped due to FloodWait")
                        break
            
            task.pending_count -= 1
            self.session.add(task)
            self.session.commit()
            
            # 切换账号（轮询）
            account_index += 1
        
        return result
    
    async def _invite_single_user(
        self,
        task: InviteTask,
        account: Account,
        target: TargetUser,
        channel_link: str,
        min_delay: int = 30,
        max_delay: int = 120
    ) -> Dict[str, Any]:
        """
        邀请单个用户
        
        Returns:
            {"status": "success/failed", "error_code": ..., "error_message": ...}
        """
        start_time = time.time()
        result = {
            "status": "failed",
            "error_code": None,
            "error_message": None,
            "duration_ms": 0,
            "flood_wait_seconds": None
        }
        
        # 随机延迟
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        
        # 定义 Pyrogram 操作
        async def op(client, link, user):
            try:
                chat = await client.get_chat(link)
                user_identifier = user.username or user.telegram_id
                await client.add_chat_members(chat_id=chat.id, user_ids=user_identifier)
                return True, {"chat_id": chat.id}
            except Exception as e:
                return False, str(e)
        
        try:
            success, res = await _create_client_and_run(
                account, op, channel_link, target, db_session=self.session
            )
            
            if success:
                result["status"] = "success"
            else:
                error_code, flood_wait = parse_error_code(str(res))
                result["error_code"] = error_code
                result["error_message"] = str(res)[:500]
                result["flood_wait_seconds"] = flood_wait
                
        except Exception as e:
            error_str = str(e)
            error_code, flood_wait = parse_error_code(error_str)
            result["error_code"] = error_code
            result["error_message"] = error_str[:500]
            result["flood_wait_seconds"] = flood_wait
        
        result["duration_ms"] = int((time.time() - start_time) * 1000)
        
        # 记录日志
        self._log_invite(task, account, target, channel_link, result)
        
        # 更新目标用户状态
        self._update_target_status(target, account, channel_link, result)
        
        return result
    
    def _log_invite(
        self,
        task: InviteTask,
        account: Account,
        target: TargetUser,
        channel_link: str,
        result: Dict
    ):
        """记录邀请日志"""
        log = InviteLog(
            task_id=task.id,
            account_id=account.id,
            target_user_id=target.id,
            target_telegram_id=target.telegram_id,
            target_username=target.username,
            target_channel=channel_link,
            status=result["status"],
            error_code=result.get("error_code"),
            error_message=result.get("error_message"),
            duration_ms=result.get("duration_ms"),
            account_username=account.username,
            flood_wait_seconds=result.get("flood_wait_seconds")
        )
        self.session.add(log)
        self.session.commit()
    
    def _update_target_status(
        self,
        target: TargetUser,
        account: Account,
        channel_link: str,
        result: Dict
    ):
        """更新目标用户的邀请状态"""
        target.invite_attempted_at = datetime.utcnow()
        target.invite_account_id = account.id
        target.invite_attempt_count += 1
        
        if result["status"] == "success":
            target.invite_status = "success"
            target.invite_success_at = datetime.utcnow()
            target.invite_target_group = channel_link
        else:
            target.invite_status = result.get("error_code", "other_error")
            target.invite_error_code = result.get("error_code")
            target.invite_error_message = result.get("error_message")
        
        self.session.add(target)
        self.session.commit()
    
    # ==================== 统计查询 ====================
    
    def get_task_stats(self, task_id: int) -> InviteStats:
        """获取任务统计 - uses GROUP BY aggregation instead of loading all logs"""
        # Count by status
        status_counts = self.session.exec(
            select(InviteLog.status, func.count(InviteLog.id)).where(
                InviteLog.task_id == task_id
            ).group_by(InviteLog.status)
        ).all()

        # Count by error_code for failed logs
        error_counts = self.session.exec(
            select(InviteLog.error_code, func.count(InviteLog.id)).where(
                InviteLog.task_id == task_id,
                InviteLog.status != "success"
            ).group_by(InviteLog.error_code)
        ).all()

        stats = InviteStats()

        # Process status counts
        for status, count in status_counts:
            stats.total += count
            if status == "success":
                stats.success += count
            else:
                stats.failed += count

        # Process error code counts
        error_map = dict(error_counts)
        stats.privacy_restricted = error_map.get("privacy_restricted", 0)
        stats.peer_flood = error_map.get("peer_flood", 0)
        stats.user_banned = error_map.get("banned", 0)
        stats.other_errors = stats.failed - stats.privacy_restricted - stats.peer_flood - stats.user_banned

        if stats.total > 0:
            stats.success_rate = round(stats.success / stats.total * 100, 2)

        return stats
    
    def get_recent_logs(self, task_id: int, limit: int = 50) -> List[InviteLog]:
        """获取最近的邀请日志"""
        return list(self.session.exec(
            select(InviteLog)
            .where(InviteLog.task_id == task_id)
            .order_by(InviteLog.created_at.desc())
            .limit(limit)
        ).all())
