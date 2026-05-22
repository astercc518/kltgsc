"""add activation_code table + subscription activated_via columns for Epic 1

Revision ID: a4b5c6d7e8f9
Revises: e4f5a6b7c8d9
Create Date: 2026-05-22

Epic 1 — bearer activation codes for subscription redemption.
Codes are admin-batch-generated, customer-redeemed in portal.
The activated_via column distinguishes USDT vs code vs admin_manual
activation sources sharing the same Subscription pipeline.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New table: activation_code
    op.execute("""
        CREATE TABLE IF NOT EXISTS activation_code (
            id SERIAL PRIMARY KEY,
            code VARCHAR(32) NOT NULL UNIQUE,
            plan VARCHAR(20) NOT NULL,
            duration_days INTEGER NOT NULL DEFAULT 30,
            batch_id VARCHAR(36) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'unused',
            created_by_admin_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
            redeemed_by_customer_id INTEGER REFERENCES customer(id) ON DELETE SET NULL,
            redeemed_subscription_id INTEGER REFERENCES subscription(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            redeemed_at TIMESTAMP,
            notes VARCHAR(200)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_status ON activation_code(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_batch_id ON activation_code(batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_plan ON activation_code(plan)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activation_code_redeemed_by_customer_id ON activation_code(redeemed_by_customer_id)")

    # Subscription gets two new columns
    op.execute("""
        ALTER TABLE subscription
        ADD COLUMN IF NOT EXISTS activated_via VARCHAR(20) NOT NULL DEFAULT 'usdt'
    """)
    op.execute("""
        ALTER TABLE subscription
        ADD COLUMN IF NOT EXISTS activation_code_id INTEGER
            REFERENCES activation_code(id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE subscription DROP COLUMN IF EXISTS activation_code_id")
    op.execute("ALTER TABLE subscription DROP COLUMN IF EXISTS activated_via")
    op.execute("DROP TABLE IF EXISTS activation_code")
