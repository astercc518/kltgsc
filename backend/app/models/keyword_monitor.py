from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class KeywordMonitorBase(SQLModel):
    keyword: str = Field(index=True)
    match_type: str = Field(default="partial")  # exact, partial, regex, semantic
    target_groups: Optional[str] = None  # Comma separated list of group links/IDs
    action_type: str = Field(default="notify")  # notify, auto_reply, trigger_script
    reply_script_id: Optional[int] = None
    is_active: bool = Field(default=True)
    description: Optional[str] = None
    
    # === 消息转发 ===
    forward_target: Optional[str] = None  # 转发目标 (群组链接/ID/用户名)
    
    # === AI 智能回复 ===
    ai_reply_prompt: Optional[str] = None  # 自定义 AI 回复提示词
    
    # === 防骚扰机制 ===
    cooldown_seconds: int = Field(default=300)  # 冷却时间 (默认5分钟)
    
    # === 自动线索录入 ===
    auto_capture_lead: bool = Field(default=False)  # 自动将命中用户加入 CRM
    
    # === 评分权重 ===
    score_weight: int = Field(default=10)  # 此关键词命中的评分权重
    
    # ============================================
    # === 被动式营销 - 方案A两级过滤 ===
    # ============================================
    # 语义匹配模式 (match_type="semantic" 时生效)
    scenario_description: Optional[str] = None  # 业务场景描述 (AI 理解的目标)
    auto_keywords: Optional[str] = None  # AI 自动生成的关键词 (JSON数组格式, 用于Level1粗筛)
    similarity_threshold: int = Field(default=70)  # 语义相似度阈值 (0-100, Level2精判)
    
    # ============================================
    # === 主动式营销模式 ===
    # ============================================
    marketing_mode: str = Field(default="passive")  # passive(被动) / active(主动)
    reply_mode: str = Field(default="group_reply")  # group_reply(群内回复) / private_dm(私聊)
    
    # 随机延迟 (模拟真人)
    delay_min_seconds: int = Field(default=30)  # 最小延迟秒数
    delay_max_seconds: int = Field(default=180)  # 最大延迟秒数
    
    # 账号轮询与熔断
    enable_account_rotation: bool = Field(default=False)  # 启用多账号轮询
    max_replies_per_day: int = Field(default=10)  # 单规则每日最大回复次数 (熔断阈值)
    daily_reply_count: int = Field(default=0)  # 当日已回复次数 (运行时更新)
    last_reply_date: Optional[str] = None  # 上次回复日期 (用于重置计数)
    
    # AI 人设预设
    ai_persona: str = Field(default="helpful")  # helpful(热心群友) / expert(行业老鸟) / curious(好奇小白) / custom(自定义)

class KeywordMonitor(KeywordMonitorBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    hits: List["KeywordHit"] = Relationship(back_populates="keyword_monitor")

class KeywordMonitorCreate(KeywordMonitorBase):
    pass

class KeywordMonitorRead(KeywordMonitorBase):
    id: int
    created_at: datetime

class KeywordMonitorUpdate(SQLModel):
    keyword: Optional[str] = None
    match_type: Optional[str] = None
    target_groups: Optional[str] = None
    action_type: Optional[str] = None
    reply_script_id: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    forward_target: Optional[str] = None
    ai_reply_prompt: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    auto_capture_lead: Optional[bool] = None
    score_weight: Optional[int] = None
    # 被动式营销 - 语义匹配
    scenario_description: Optional[str] = None
    auto_keywords: Optional[str] = None
    similarity_threshold: Optional[int] = None
    # 主动式营销
    marketing_mode: Optional[str] = None
    reply_mode: Optional[str] = None
    delay_min_seconds: Optional[int] = None
    delay_max_seconds: Optional[int] = None
    enable_account_rotation: Optional[bool] = None
    max_replies_per_day: Optional[int] = None
    ai_persona: Optional[str] = None


class KeywordHitBase(SQLModel):
    keyword_monitor_id: Optional[int] = Field(default=None, foreign_key="keywordmonitor.id")
    source_group_id: str
    source_group_name: Optional[str] = None
    source_user_id: str
    source_user_name: Optional[str] = None
    message_content: str
    message_id: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending")  # pending, handled, ignored

class KeywordHit(KeywordHitBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    keyword_monitor: Optional[KeywordMonitor] = Relationship(back_populates="hits")

class KeywordHitRead(KeywordHitBase):
    id: int
    keyword_monitor: Optional[KeywordMonitorRead] = None
