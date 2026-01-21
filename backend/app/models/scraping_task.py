from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class ScrapingTaskBase(SQLModel):
    task_type: str  # join_group, join_batch, scrape_members
    status: str = Field(default="pending")  # pending, running, completed, failed
    account_ids_json: str = "[]"  # JSON array of account ids used
    group_links_json: str = "[]"  # JSON array of group links
    result_json: str = "{}"  # JSON result details
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None

class ScrapingTask(ScrapingTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

class ScrapingTaskCreate(ScrapingTaskBase):
    pass

class ScrapingTaskRead(ScrapingTaskBase):
    id: int
    created_at: datetime
    completed_at: Optional[datetime] = None
