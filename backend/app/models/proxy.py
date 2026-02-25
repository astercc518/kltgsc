from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class ProxyBase(SQLModel):
    ip: str = Field(index=True)
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = Field(default="socks5")
    status: str = Field(default="active", index=True)  # active, dead - 添加索引
    category: str = Field(default="static", index=True)  # static, rotating - 添加索引
    provider_type: str = Field(default="datacenter", index=True)  # isp, datacenter - 添加索引
    country: Optional[str] = Field(default=None, index=True)  # 添加索引用于按国家筛选
    fail_count: int = Field(default=0)
    last_checked: Optional[datetime] = Field(default=None, index=True)  # 添加索引
    expire_time: Optional[datetime] = Field(default=None, index=True)  # 添加索引用于过期检查


class Proxy(ProxyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, index=True)  # 添加索引
    
    accounts: List["Account"] = Relationship(back_populates="proxy")

class ProxyCreate(ProxyBase):
    pass

class ProxyRead(ProxyBase):
    id: int
    created_at: Optional[datetime] = None