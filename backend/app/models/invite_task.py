from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import BigInteger, Column, Text
from datetime import datetime

class InviteTaskBase(SQLModel):
    """批量拉人任务"""
    name: str
    target_channel: str  # 目标群/频道链接
    source_group: Optional[str] = None  # 可选：用于筛选目标用户的来源群
    status: str = Field(default="pending", index=True)  # pending, running, paused, completed, failed
    
    # === 账号与目标配置 ===
    account_ids_json: str = "[]"  # 使用的账号ID列表
    target_user_ids_json: str = "[]"  # 目标用户ID列表
    account_group: Optional[str] = Field(default=None, index=True)  # 账号组名称（可选，用于动态分配）
    
    # === 执行统计 ===
    total_count: int = Field(default=0)  # 总目标数
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    privacy_restricted_count: int = Field(default=0)  # 隐私限制
    flood_wait_count: int = Field(default=0)  # 触发风控次数
    pending_count: int = Field(default=0)  # 待执行数
    
    # === 延迟策略（秒）===
    min_delay: int = Field(default=30)  # 最小间隔（建议30秒以上）
    max_delay: int = Field(default=120)  # 最大间隔
    
    # === 安全限制 ===
    max_invites_per_account: int = Field(default=20)  # 每账号每日最大拉人数
    max_invites_per_task: int = Field(default=100)  # 单任务最大拉人数
    concurrent_accounts: int = Field(default=1)  # 同时使用的账号数
    stop_on_flood: bool = Field(default=True)  # 遇到 FloodWait 是否停止任务
    
    # === 高级筛选 ===
    filter_tags: Optional[str] = None  # JSON: 只拉有特定标签的用户，如 ["high_quality"]
    filter_min_score: Optional[int] = None  # 只拉评分大于等于此值的用户
    filter_funnel_stages: Optional[str] = None  # JSON: 筛选漏斗阶段，如 ["raw", "qualified"]
    exclude_invited: bool = Field(default=True)  # 排除已成功拉过的用户
    exclude_failed_recently: bool = Field(default=True)  # 排除近期拉失败的用户
    failed_cooldown_hours: int = Field(default=72)  # 失败用户冷却时间（小时）
    
    # === 定时调度 ===
    scheduled_at: Optional[datetime] = None  # 定时开始时间
    is_recurring: bool = Field(default=False)  # 是否循环任务
    recurring_interval_hours: int = Field(default=24)  # 循环间隔（小时）
    recurring_batch_size: int = Field(default=50)  # 每次循环拉人数
    
    # === 时间戳 ===
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))  # 最后错误信息


class InviteTask(InviteTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class InviteTaskCreate(SQLModel):
    """创建拉人任务的请求体"""
    name: str
    target_channel: str
    source_group: Optional[str] = None
    
    # 可以通过 ID 列表或账号组指定账号
    account_ids: Optional[List[int]] = None
    account_group: Optional[str] = None
    
    # 可以通过 ID 列表或高级筛选指定目标用户
    target_user_ids: Optional[List[int]] = None
    
    # 高级筛选（当不指定 target_user_ids 时使用）
    filter_tags: Optional[List[str]] = None
    filter_min_score: Optional[int] = None
    filter_funnel_stages: Optional[List[str]] = None
    filter_source_groups: Optional[List[str]] = None  # 筛选来源群
    max_targets: int = 100  # 筛选结果最大数量
    
    # 策略配置
    min_delay: int = 30
    max_delay: int = 120
    max_invites_per_account: int = 20
    max_invites_per_task: int = 100
    concurrent_accounts: int = 1
    stop_on_flood: bool = True
    exclude_invited: bool = True
    exclude_failed_recently: bool = True
    failed_cooldown_hours: int = 72
    
    # 定时调度
    scheduled_at: Optional[datetime] = None
    is_recurring: bool = False
    recurring_interval_hours: int = 24
    recurring_batch_size: int = 50


class InviteTaskRead(InviteTaskBase):
    id: int
    # 计算字段
    progress_percent: Optional[float] = None
    estimated_remaining_minutes: Optional[int] = None


class InviteTaskUpdate(SQLModel):
    """更新拉人任务（暂停/恢复/取消）"""
    status: Optional[str] = None  # paused, running, cancelled
    min_delay: Optional[int] = None
    max_delay: Optional[int] = None
