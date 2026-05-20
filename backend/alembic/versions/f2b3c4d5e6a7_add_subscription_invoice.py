"""add subscription + invoice tables for Epic 2 billing

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-05-18

TG1.AI Epic 2 (USDT manual confirmation MVP):
- subscription: a customer's billing window (plan + period + status)
- invoice: one-shot USDT bill, manually confirmed by admin via tx_hash

Tables are also auto-created by SQLModel.create_all on app startup; this
migration guarantees structural compatibility via IF NOT EXISTS.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f2b3c4d5e6a7'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS subscription (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
            plan VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            auto_renew BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            canceled_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscription_customer_id ON subscription(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscription_status ON subscription(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscription_plan ON subscription(plan)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscription_created_at ON subscription(created_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS invoice (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
            subscription_id INTEGER REFERENCES subscription(id) ON DELETE SET NULL,
            plan VARCHAR(20) NOT NULL,
            amount_usd DOUBLE PRECISION NOT NULL,
            amount_crypto DOUBLE PRECISION NOT NULL,
            currency VARCHAR(10) NOT NULL DEFAULT 'USDT',
            network VARCHAR(10) NOT NULL DEFAULT 'TRC20',
            payment_address VARCHAR(200) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            tx_hash VARCHAR(200),
            description VARCHAR(200) NOT NULL,
            paid_at TIMESTAMP,
            paid_by_admin INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_customer_id ON invoice(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_subscription_id ON invoice(subscription_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_status ON invoice(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_network ON invoice(network)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_created_at ON invoice(created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invoice CASCADE")
    op.execute("DROP TABLE IF EXISTS subscription CASCADE")
