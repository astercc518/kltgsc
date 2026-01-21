from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class ProxyBase(SQLModel):
    ip: str = Field(index=True)
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = Field(default="socks5")
    status: str = Field(default="active")  # active, dead
    category: str = Field(default="static") # static (long-term), rotating (short-term)
    provider_type: str = Field(default="datacenter") # isp, datacenter
    country: Optional[str] = None  # 国家/地区
    fail_count: int = Field(default=0)
    last_checked: Optional[datetime] = None
    expire_time: Optional[datetime] = None

class Proxy(ProxyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    accounts: List["Account"] = Relationship(back_populates="proxy")

class ProxyCreate(ProxyBase):
    pass

class ProxyRead(ProxyBase):
    id: int
    created_at: Optional[datetime] = None