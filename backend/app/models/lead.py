from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class LeadBase(SQLModel):
    account_id: Optional[int] = Field(default=None, index=True, foreign_key="account.id")
    telegram_user_id: int = Field(index=True)
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    status: str = Field(default="new") # new, contacted, replied, interested, converted, closed
    tags_json: str = "[]" # ["high_value", "spam"]
    notes: Optional[str] = None
    last_interaction_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ── 销售接管 / AI 副驾驶 ──
    assigned_to_user_id: Optional[int] = Field(
        default=None, foreign_key="user.id", index=True
    )
    ai_enabled: bool = Field(default=True)
    ai_draft: Optional[str] = None  # 最新一条 AI 建议草稿（接管后才生成）
    claimed_at: Optional[datetime] = None

    # 多租户归属（TG1.AI 商业化）— 沿 Account.customer_id 派生，但显式存便于查询
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id", index=True)

    # ── Epic 5.2: 主号通知 + 对接群超时升级 ──
    main_account_notified_at: Optional[datetime] = None
    handover_link_sent_at: Optional[datetime] = None
    # denormalized 在 Lead 上以便 Celery task 用 SELECT FOR UPDATE 防 race
    takeover_deadline: Optional[datetime] = Field(default=None, index=True)

    # ── Bulk Send W2: 区分 lead 来源 + 反查 batch ──
    # source: 'monitor' (现有关键词监控) | 'bulk' (bulk send 回复) | 其他
    source: str = Field(default="monitor", max_length=20, index=True)
    bulk_batch_id: Optional[int] = Field(default=None, foreign_key="bulk_batch.id", index=True)

    # ── Epic D: 业务分类 + 查看计费 ──
    # industry: 主分类（与 Customer.industry 同枚举），用于销售按业务过滤
    # category: 自由文本二级分类（销售自定义）
    # view_count: 累计被查看次数（每次 /sales/leads/{id}/view 调用 +1）
    industry: Optional[str] = Field(default=None, max_length=50, index=True)
    category: Optional[str] = Field(default=None, max_length=50, index=True)
    view_count: int = Field(default=0)

class Lead(LeadBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    interactions: List["LeadInteraction"] = Relationship(back_populates="lead")

class LeadCreate(LeadBase):
    pass

class LeadRead(LeadBase):
    id: int

class LeadInteractionBase(SQLModel):
    lead_id: int = Field(foreign_key="lead.id")
    direction: str # inbound (user -> bot), outbound (bot -> user)
    message_type: str = Field(default="text") # text, photo, file
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class LeadInteraction(LeadInteractionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lead: Optional[Lead] = Relationship(back_populates="interactions")

class LeadInteractionCreate(LeadInteractionBase):
    pass

class LeadInteractionRead(LeadInteractionBase):
    id: int


class LeadDetail(LeadRead):
    interactions: List[LeadInteractionRead] = Field(default_factory=list)
