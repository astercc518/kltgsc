"""
Subscription + Invoice models — Epic 2 billing core.

Design notes (MVP scope, [[project-payment-decision]] = USDT, no Stripe):

* Subscription = a customer's active billing window (period_start..period_end).
  Customer.plan / subscription_status / current_period_end are denormalized
  copies of the active Subscription, refreshed by `activate_subscription`
  service so customer-facing reads stay cheap.
* Invoice = one-shot bill (initial purchase / renewal / add-on). Customer
  pays USDT to a static platform address; admin manually confirms the
  on-chain tx hash via /admin/customers/{id}/activate-subscription.
* Amount disambiguation: the customer is asked to pay `amount_crypto`
  (= amount_usd + random 0.01-0.99 suffix). The unique suffix lets ops
  match an incoming transfer to a specific invoice without per-customer
  HD-wallet addresses. Collisions across pending invoices are avoided
  at create time.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ── Subscription status ───────────────────────────────────────────────
SUB_PENDING = "pending"     # 已下单未付款
SUB_ACTIVE = "active"       # 已支付，配额生效中
SUB_CANCELED = "canceled"   # 客户主动取消
SUB_EXPIRED = "expired"     # 周期到期未续费
SUBSCRIPTION_STATUSES = {SUB_PENDING, SUB_ACTIVE, SUB_CANCELED, SUB_EXPIRED}


# ── Invoice status ────────────────────────────────────────────────────
INV_PENDING = "pending"     # 等待客户付款
INV_PAID = "paid"           # 已确认到账
INV_EXPIRED = "expired"     # 30 分钟未付款
INV_REFUNDED = "refunded"
INVOICE_STATUSES = {INV_PENDING, INV_PAID, INV_EXPIRED, INV_REFUNDED}


# ── USDT networks ─────────────────────────────────────────────────────
NETWORK_TRC20 = "TRC20"     # 推荐：手续费最低
NETWORK_ERC20 = "ERC20"
NETWORK_BEP20 = "BEP20"
NETWORKS = {NETWORK_TRC20, NETWORK_ERC20, NETWORK_BEP20}


class Subscription(SQLModel, table=True):
    __tablename__ = "subscription"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)

    plan: str = Field(index=True, max_length=20)  # starter / growth / pro
    status: str = Field(default=SUB_PENDING, index=True, max_length=20)

    period_start: datetime
    period_end: datetime
    auto_renew: bool = Field(default=False)  # MVP 不做自动续费

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    activated_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None


class Invoice(SQLModel, table=True):
    __tablename__ = "invoice"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    subscription_id: Optional[int] = Field(
        default=None, foreign_key="subscription.id", index=True
    )

    plan: str = Field(max_length=20)
    amount_usd: float
    amount_crypto: float  # 实际收款金额（含尾数标识）
    currency: str = Field(default="USDT", max_length=10)
    network: str = Field(default=NETWORK_TRC20, index=True, max_length=10)
    payment_address: str = Field(max_length=200)

    status: str = Field(default=INV_PENDING, index=True, max_length=20)
    tx_hash: Optional[str] = Field(default=None, max_length=200)
    description: str = Field(max_length=200)

    paid_at: Optional[datetime] = None
    paid_by_admin: Optional[int] = Field(default=None, foreign_key="user.id")

    # Epic C2 — when set, this invoice credits a SalesWallet keyed by
    # (sales_owner_type, sales_owner_id) instead of CustomerWallet.
    # NULL → legacy customer-wallet topup or subscription invoice.
    sales_owner_type: Optional[str] = Field(default=None, max_length=20)
    sales_owner_id: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    expires_at: datetime


# ── Public read schemas ───────────────────────────────────────────────

class InvoiceRead(SQLModel):
    id: int
    customer_id: int
    subscription_id: Optional[int]
    plan: str
    amount_usd: float
    amount_crypto: float
    currency: str
    network: str
    payment_address: str
    status: str
    tx_hash: Optional[str]
    description: str
    paid_at: Optional[datetime]
    created_at: datetime
    expires_at: datetime


class SubscriptionRead(SQLModel):
    id: int
    customer_id: int
    plan: str
    status: str
    period_start: datetime
    period_end: datetime
    auto_renew: bool
    activated_at: Optional[datetime]
    created_at: datetime


class SubscribeRequest(SQLModel):
    plan: str  # starter / growth / pro
    network: str = NETWORK_TRC20  # USDT 网络


class ActivateSubscriptionRequest(SQLModel):
    invoice_id: int
    tx_hash: str
