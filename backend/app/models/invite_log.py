"""
邀请日志模型 - 记录每一次拉人操作的详细信息
用于：
1. 精细化追踪每次拉人的结果
2. 账号每日限额统计
3. 错误分析与优化
4. ROI分析
"""
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import BigInteger, Column, Text
from datetime import datetime


class InviteLogBase(SQLModel):
    """邀请操作日志"""
    # === 关联信息 ===
    task_id: int = Field(index=True)  # 关联的任务ID
    account_id: int = Field(index=True)  # 执行拉人的账号ID
    target_user_id: int = Field(index=True)  # 目标用户ID
    target_telegram_id: int = Field(sa_column=Column(BigInteger, index=True))  # Telegram用户ID
    target_username: Optional[str] = None  # 目标用户名
    
    # === 目标群信息 ===
    target_channel: str  # 目标群链接
    target_channel_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger))  # 目标群ID
    
    # === 执行结果 ===
    status: str = Field(index=True)  # success, failed, skipped
    error_code: Optional[str] = Field(default=None, index=True)
    # 常见错误代码：
    # USER_PRIVACY_RESTRICTED - 用户隐私设置禁止拉人
    # USER_BANNED_IN_CHANNEL - 用户被目标群封禁
    # USER_NOT_MUTUAL_CONTACT - 非双向联系人
    # PEER_FLOOD - 账号触发风控
    # CHAT_WRITE_FORBIDDEN - 无权操作群组
    # USER_NOT_PARTICIPANT - 用户不在来源群
    # INVITE_HASH_EXPIRED - 邀请链接过期
    # USER_ALREADY_PARTICIPANT - 用户已在群中
    
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # === 时间信息 ===
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    duration_ms: Optional[int] = None  # 操作耗时(毫秒)
    
    # === 额外上下文 ===
    account_username: Optional[str] = None  # 账号用户名（便于查看）
    retry_count: int = Field(default=0)  # 重试次数
    flood_wait_seconds: Optional[int] = None  # 如果触发FloodWait，等待秒数


class InviteLog(InviteLogBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class InviteLogCreate(SQLModel):
    """创建邀请日志"""
    task_id: int
    account_id: int
    target_user_id: int
    target_telegram_id: int
    target_username: Optional[str] = None
    target_channel: str
    target_channel_id: Optional[int] = None
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    account_username: Optional[str] = None
    retry_count: int = 0
    flood_wait_seconds: Optional[int] = None


class InviteLogRead(InviteLogBase):
    id: int


# === 统计相关模型 ===

class InviteStats(SQLModel):
    """邀请统计（用于API响应）"""
    total: int = 0
    success: int = 0
    failed: int = 0
    privacy_restricted: int = 0
    peer_flood: int = 0
    user_banned: int = 0
    other_errors: int = 0
    success_rate: float = 0.0


class AccountInviteStats(SQLModel):
    """账号邀请统计"""
    account_id: int
    account_username: Optional[str] = None
    today_count: int = 0
    today_success: int = 0
    today_failed: int = 0
    total_count: int = 0
    total_success: int = 0
    last_invite_at: Optional[datetime] = None
    last_flood_at: Optional[datetime] = None  # 最后触发风控时间
    cooldown_until: Optional[datetime] = None  # 冷却截止时间
    is_available: bool = True  # 是否可用于拉人
