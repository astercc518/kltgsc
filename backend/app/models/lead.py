from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class LeadBase(SQLModel):
    account_id: int = Field(index=True, foreign_key="account.id")
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
