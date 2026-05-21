"""
Customer-facing scrape batch model.

The admin-side `ScrapingTask` table stays as-is (generic task tracking that
mixes join + scrape across all internal accounts). `ScrapeBatch` is the
customer view: one row per Portal-initiated scrape job, tied to a customer
and charged from their wallet on completion (1¢ × member by default —
configurable via FeatureRegistry slug 'scrape_group_members').
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


SCRAPE_PENDING = "pending"
SCRAPE_RUNNING = "running"
SCRAPE_COMPLETED = "completed"
SCRAPE_FAILED = "failed"
SCRAPE_CANCELED = "canceled"

SCRAPE_STATUSES = {
    SCRAPE_PENDING, SCRAPE_RUNNING, SCRAPE_COMPLETED, SCRAPE_FAILED, SCRAPE_CANCELED,
}


class ScrapeBatch(SQLModel, table=True):
    __tablename__ = "scrape_batch"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)

    name: str = Field(max_length=120)
    # JSON-serialized list of t.me/foo links
    source_links_json: str = Field(default="[]")
    # JSON array of account IDs picked from the customer's pool (empty = auto)
    account_ids_json: str = Field(default="[]")

    limit_per_group: int = Field(default=200, ge=1, le=10000)
    filter_active_only: bool = Field(default=False)
    filter_has_photo: bool = Field(default=False)
    filter_has_username: bool = Field(default=False)

    status: str = Field(default=SCRAPE_PENDING, max_length=20, index=True)

    # Cost accounting
    estimated_unit_price_cents: int = Field(default=1)
    estimated_total_cents: int = Field(default=0)
    charged_cents: int = Field(default=0)

    # Progress
    scraped_count: int = Field(default=0)
    new_users_count: int = Field(default=0)
    failed_group_count: int = Field(default=0)

    # Linkage to internal scraping_task row (so admin can see the celery side)
    scraping_task_id: Optional[int] = Field(default=None, foreign_key="scrapingtask.id")
    celery_task_id: Optional[str] = Field(default=None, max_length=64)

    error_message: Optional[str] = Field(default=None, max_length=500)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ── API schemas ────────────────────────────────────────────────────────


class ScrapeBatchCreate(BaseModel):
    name: str
    source_links: List[str]
    account_ids: Optional[List[int]] = None
    limit_per_group: int = 200
    filter_active_only: bool = False
    filter_has_photo: bool = False
    filter_has_username: bool = False


class ScrapeBatchRead(BaseModel):
    id: int
    customer_id: int
    name: str
    source_links: List[str]
    account_ids: List[int]
    limit_per_group: int
    filter_active_only: bool
    filter_has_photo: bool
    filter_has_username: bool
    status: str
    estimated_unit_price_cents: int
    estimated_total_cents: int
    charged_cents: int
    scraped_count: int
    new_users_count: int
    failed_group_count: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_orm_with_json(cls, b: ScrapeBatch) -> "ScrapeBatchRead":
        import json
        return cls(
            id=b.id,
            customer_id=b.customer_id,
            name=b.name,
            source_links=json.loads(b.source_links_json or "[]"),
            account_ids=json.loads(b.account_ids_json or "[]"),
            limit_per_group=b.limit_per_group,
            filter_active_only=b.filter_active_only,
            filter_has_photo=b.filter_has_photo,
            filter_has_username=b.filter_has_username,
            status=b.status,
            estimated_unit_price_cents=b.estimated_unit_price_cents,
            estimated_total_cents=b.estimated_total_cents,
            charged_cents=b.charged_cents,
            scraped_count=b.scraped_count,
            new_users_count=b.new_users_count,
            failed_group_count=b.failed_group_count,
            error_message=b.error_message,
            started_at=b.started_at,
            completed_at=b.completed_at,
            created_at=b.created_at,
        )


class ScrapeCostPreview(BaseModel):
    estimated_member_count: int     # limit_per_group × len(source_links)
    unit_price_cents: int
    estimated_total_cents: int
    balance_cents: int
    balance_sufficient: bool
    shortfall_cents: int
