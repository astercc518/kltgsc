"""
Customer Wallet — Phase 1 of TG Bulk Send (W1)

- CustomerWallet: 一对一关联 customer，存余额 + 累计统计（cents 整数）
- WalletTransaction: 流水（充值/扣款/退款/调整）
- 余额变动必须走 transaction，幂等通过 idempotency_key 保证

参考 docs/planning/bulk_send_spec.md §3.1
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

TXN_TOPUP = "topup"
TXN_CHARGE = "charge"
TXN_REFUND = "refund"
TXN_ADJUST = "adjust"

TXN_TYPES = {TXN_TOPUP, TXN_CHARGE, TXN_REFUND, TXN_ADJUST}


class CustomerWallet(SQLModel, table=True):
    __tablename__ = "customer_wallet"

    customer_id: int = Field(
        primary_key=True, foreign_key="customer.id", index=True
    )

    balance_cents: int = Field(default=0, ge=0)
    total_topup_cents: int = Field(default=0, ge=0)
    total_spent_cents: int = Field(default=0, ge=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WalletTransaction(SQLModel, table=True):
    __tablename__ = "wallet_transaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)

    type: str = Field(max_length=20, index=True)  # TXN_*
    amount_cents: int  # +入账，-扣账
    balance_after_cents: int  # 操作后余额快照（便于审计）

    description: str = Field(default="", max_length=200)

    bulk_batch_id: Optional[int] = Field(default=None, index=True)
    invoice_id: Optional[int] = Field(
        default=None, foreign_key="invoice.id", index=True
    )

    # 幂等键：上游可重复请求但只生效一次
    idempotency_key: str = Field(unique=True, max_length=120)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ── Public read/write schemas ─────────────────────────────────────────


class WalletRead(SQLModel):
    customer_id: int
    balance_cents: int
    total_topup_cents: int
    total_spent_cents: int
    created_at: datetime
    updated_at: datetime


class WalletTransactionRead(SQLModel):
    id: int
    type: str
    amount_cents: int
    balance_after_cents: int
    description: str
    bulk_batch_id: Optional[int]
    invoice_id: Optional[int]
    created_at: datetime


class WalletTopupRequest(SQLModel):
    """客户发起充值，创建 USDT invoice"""
    amount_usd: float = Field(ge=100, le=50000)  # $100-50000 限额
    network: str = Field(default="TRC20", max_length=10)


class WalletTopupResponse(SQLModel):
    """返回支付指令"""
    invoice_id: int
    amount_usd: float
    amount_crypto: float
    bonus_pct: int  # 赠送百分比（0/2/5/10）
    bonus_cents: int  # 赠送金额（cents）
    final_credit_cents: int  # 到账总余额（含赠送）
    currency: str
    network: str
    payment_address: str
    expires_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────


def calculate_bonus_pct(amount_usd: float) -> int:
    """充值赠送阶梯"""
    if amount_usd >= 5000:
        return 10
    if amount_usd >= 1000:
        return 5
    if amount_usd >= 500:
        return 2
    return 0


def calculate_tier_unit_price_cents(total_spent_cents: int) -> int:
    """按累计已发送量计算下一条单价（cents）"""
    spent_usd = total_spent_cents / 100
    # 转 cents：$0.15 = 15, $0.10 = 10, $0.07 = 7, $0.05 = 5
    if spent_usd < 1500:  # < $1500 已花掉 ≈ 10K 条 @ $0.15
        return 15
    if spent_usd < 6500:  # < $6500 ≈ 50K 条 @ $0.10
        return 10
    if spent_usd < 16500:  # < $16500 ≈ 200K 条 @ $0.07
        return 7
    return 5
