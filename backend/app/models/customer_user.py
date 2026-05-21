"""
CustomerUser — a sub-user (employee) inside a Customer tenant.

Epic C1 of the marketing-assistant module. Each customer can hire its own
salespeople; they log in via the same /auth/login endpoint (identifier is
email containing '@', resolution order: Customer → CustomerUser) but get a
separate JWT type ('customer_sales') that scopes lead visibility to the
parent customer and bills lead-view charges to the user's personal wallet
(Epic C2 / D).

Note: this is distinct from User.role='sales' (platform employees that
work across all customers). The marketing-assistant Portal supports both,
unified through deps_sales.get_current_sales.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator
from sqlmodel import Field, SQLModel


CU_ROLE_SALES = "sales"   # only role for now; reserved for future expansion
CU_ROLES = {CU_ROLE_SALES}


class CustomerUser(SQLModel, table=True):
    __tablename__ = "customer_user"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    email: str = Field(unique=True, index=True, max_length=120)
    hashed_password: str

    name: Optional[str] = Field(default=None, max_length=120)
    role: str = Field(default=CU_ROLE_SALES, max_length=20)

    # JSON-serialized list of Lead.industry values this sales user wants to see
    # (empty list = no filter, see all of parent customer's leads).
    industry_filter_json: str = Field(default="[]")

    enabled: bool = Field(default=True)
    last_login_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ── API schemas ────────────────────────────────────────────────────────


class CustomerUserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = None
    industry_filter: List[str] = []

    @field_validator("email")
    @classmethod
    def _email_has_at(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if "@" not in v or "." not in v.split("@", 1)[-1]:
            raise ValueError("invalid email")
        return v


class CustomerUserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    industry_filter: Optional[List[str]] = None
    enabled: Optional[bool] = None


class CustomerUserRead(BaseModel):
    id: int
    customer_id: int
    email: str
    name: Optional[str]
    role: str
    industry_filter: List[str]
    enabled: bool
    last_login_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_orm_with_json(cls, u: CustomerUser) -> "CustomerUserRead":
        import json
        return cls(
            id=u.id,
            customer_id=u.customer_id,
            email=u.email,
            name=u.name,
            role=u.role,
            industry_filter=json.loads(u.industry_filter_json or "[]"),
            enabled=u.enabled,
            last_login_at=u.last_login_at,
            created_at=u.created_at,
        )
