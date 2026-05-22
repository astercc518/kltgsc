"""
ActivationCode — bearer redemption code for subscription activation.

Epic 1 — admin generates a batch of codes for a given plan, distributes
them out-of-band (email/IM/etc.), and any customer who submits an unused
code via /customer/redeem-code claims an active Subscription on that
plan. See docs/superpowers/plans/2026-05-22-epic1-levels-and-activation-codes.md
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ── State machine ──────────────────────────────────────────────────────
CODE_UNUSED = "unused"
CODE_REDEEMED = "redeemed"
CODE_REVOKED = "revoked"
CODE_STATUSES = {CODE_UNUSED, CODE_REDEEMED, CODE_REVOKED}


class ActivationCode(SQLModel, table=True):
    __tablename__ = "activation_code"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=32)
    plan: str = Field(index=True, max_length=20)  # starter / growth / pro
    duration_days: int = Field(default=30)
    batch_id: str = Field(index=True, max_length=36)  # UUID4 hex, groups codes from one generate call
    status: str = Field(default=CODE_UNUSED, index=True, max_length=20)

    created_by_admin_id: Optional[int] = Field(default=None, foreign_key="user.id")
    redeemed_by_customer_id: Optional[int] = Field(
        default=None, foreign_key="customer.id", index=True
    )
    redeemed_subscription_id: Optional[int] = Field(
        default=None, foreign_key="subscription.id"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    redeemed_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=200)


# ── Request / response schemas ─────────────────────────────────────────

class ActivationCodeGenerateRequest(SQLModel):
    plan: str
    count: int = Field(default=1, ge=1, le=500)
    duration_days: int = Field(default=30, ge=1, le=365)
    notes: Optional[str] = None


class ActivationCodeRead(SQLModel):
    id: int
    code: str
    plan: str
    duration_days: int
    batch_id: str
    status: str
    created_by_admin_id: Optional[int]
    redeemed_by_customer_id: Optional[int]
    redeemed_subscription_id: Optional[int]
    created_at: datetime
    redeemed_at: Optional[datetime]
    notes: Optional[str]


class ActivationCodeGenerateResponse(SQLModel):
    batch_id: str
    codes: list[ActivationCodeRead]


class ActivationCodeRedeemRequest(SQLModel):
    code: str
