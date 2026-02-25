"""
账号发送统计模型
用于跟踪每个账号的发送行为，防止封号
"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, date


class AccountSendStats(SQLModel, table=True):
    """账号每日发送统计"""
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    stat_date: date = Field(index=True)  # 统计日期
    
    # 发送计数
    send_count: int = Field(default=0)  # 今日已发送数量
    success_count: int = Field(default=0)  # 成功数量
    fail_count: int = Field(default=0)  # 失败数量
    
    # 时间追踪
    last_send_at: Optional[datetime] = None  # 最后一次发送时间
    first_send_at: Optional[datetime] = None  # 今日首次发送时间
    
    # 连续发送计数（用于休息判断）
    consecutive_sends: int = Field(default=0)  # 连续发送次数
    last_rest_at: Optional[datetime] = None  # 最后一次休息时间
    
    # 风险标记
    flood_wait_count: int = Field(default=0)  # 今日触发 FloodWait 次数
    error_count: int = Field(default=0)  # 今日错误次数
    
    class Config:
        # 联合唯一索引：每个账号每天只有一条记录
        table_name = "accountsendstats"


class AccountSendStatsRead(SQLModel):
    """读取模型"""
    id: int
    account_id: int
    stat_date: date
    send_count: int
    success_count: int
    fail_count: int
    last_send_at: Optional[datetime]
    consecutive_sends: int
    flood_wait_count: int
