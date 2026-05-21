"""
Sales wallet — personal balance for marketing-assistant sales identities.

Epic C2 of the marketing-assistant module. Distinct from CustomerWallet
because sales topups are personal (the salesperson pays for their own
lead-view consumption) and need to be isolated from the customer's
group-control wallet.

A SalesWallet is keyed by (owner_type, owner_id) so the same table holds
both kinds:
  - owner_type='customer_sales', owner_id=CustomerUser.id
  - owner_type='platform_sales',  owner_id=User.id

Topup uses the existing Invoice flow (USDT via NowPayments). When an
invoice with the sales_owner_* columns set is marked paid, the credit
routes to the matching SalesWallet (see webhooks / billing_service).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import PrimaryKeyConstraint
from sqlmodel import Field, SQLModel


OWNER_CUSTOMER_SALES = "customer_sales"
OWNER_PLATFORM_SALES = "platform_sales"
SALES_OWNER_TYPES = {OWNER_CUSTOMER_SALES, OWNER_PLATFORM_SALES}


class SalesWallet(SQLModel, table=True):
    __tablename__ = "sales_wallet"
    __table_args__ = (
        PrimaryKeyConstraint("owner_type", "owner_id"),
    )

    owner_type: str = Field(max_length=20)
    owner_id: int = Field(index=True)

    balance_cents: int = Field(default=0, ge=0)
    total_topup_cents: int = Field(default=0, ge=0)
    total_spent_cents: int = Field(default=0, ge=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SalesWalletTransaction(SQLModel, table=True):
    __tablename__ = "sales_wallet_transaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_type: str = Field(max_length=20, index=True)
    owner_id: int = Field(index=True)

    type: str = Field(max_length=20, index=True)  # topup | charge | refund | adjust
    amount_cents: int                              # +入账 / -扣账
    balance_after_cents: int

    description: str = Field(default="", max_length=200)
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id", index=True)
    lead_id: Optional[int] = Field(default=None, foreign_key="lead.id", index=True)

    idempotency_key: str = Field(unique=True, max_length=120)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ── API schemas ────────────────────────────────────────────────────────


class SalesWalletRead(SQLModel):
    owner_type: str
    owner_id: int
    balance_cents: int
    total_topup_cents: int
    total_spent_cents: int
    created_at: datetime
    updated_at: datetime


class SalesWalletTopupRequest(SQLModel):
    amount_usd: float = Field(ge=20, le=5000)  # smaller floor than customer wallet
    network: str = Field(default="TRC20", max_length=10)


class SalesWalletTransactionRead(SQLModel):
    id: int
    type: str
    amount_cents: int
    balance_after_cents: int
    description: str
    invoice_id: Optional[int]
    lead_id: Optional[int]
    created_at: datetime
