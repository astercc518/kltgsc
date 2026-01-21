from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from app.models.proxy import Proxy

class AccountBase(SQLModel):
    phone_number: str = Field(unique=True, index=True)
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    session_string: Optional[str] = None
    session_file_path: Optional[str] = None
    status: str = Field(default="init")  # init, active, banned, spam_block, flood_wait
    last_active: Optional[datetime] = None
    proxy_id: Optional[int] = Field(default=None, foreign_key="proxy.id")
    device_model: Optional[str] = None
    system_version: Optional[str] = None
    app_version: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    
    # AI fields
    auto_reply: bool = Field(default=False)
    persona_prompt: Optional[str] = None # e.g. "You are a helpful assistant..."
    
    # Management fields
    role: str = Field(default="worker", index=True) # worker, master, support
    tier: Optional[str] = Field(default="tier3", index=True) # tier1 (premium), tier2 (support/shill), tier3 (disposable)
    tags: Optional[str] = None # Comma separated tags e.g. "US,Crypto"

class Account(AccountBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    proxy: Optional[Proxy] = Relationship(back_populates="accounts")

class AccountCreate(AccountBase):
    pass

class AccountRead(AccountBase):
    id: int
    created_at: datetime
    proxy: Optional[Proxy] = None
