from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class SystemConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
