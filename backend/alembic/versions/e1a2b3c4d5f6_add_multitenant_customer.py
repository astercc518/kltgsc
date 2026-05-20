"""add multi-tenant customer + customer_id to core business tables

Revision ID: e1a2b3c4d5f6
Revises: c9a7d2e3f4b5
Create Date: 2026-05-18

Epic 1 of TG1.AI commercialization:
- customer table (tenant master) — auto-created by SQLModel.create_all on app
  startup, so this migration only guarantees structure via IF NOT EXISTS.
- customer_id FK on six core business tables. Existing rows get NULL
  (= system-owned, visible only to internal admins).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, Sequence[str], None] = 'c9a7d2e3f4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TENANT_TABLES = [
    "account",
    "lead",
    "ai_knowledge_base",
    "sourcegroup",
    "ai_persona",
    "campaign",
]


def upgrade() -> None:
    # 1) customer table: idempotent create (already auto-built by SQLModel)
    op.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR NOT NULL,
            name VARCHAR(120),
            company VARCHAR(200),
            industry VARCHAR(80),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            plan VARCHAR(20),
            subscription_status VARCHAR(20),
            current_period_end TIMESTAMP,
            account_quota INTEGER NOT NULL DEFAULT 0,
            group_quota INTEGER NOT NULL DEFAULT 0,
            token_quota INTEGER NOT NULL DEFAULT 0,
            seat_quota INTEGER NOT NULL DEFAULT 1,
            account_used INTEGER NOT NULL DEFAULT 0,
            group_used INTEGER NOT NULL DEFAULT 0,
            token_used INTEGER NOT NULL DEFAULT 0,
            last_login_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_email ON customer(email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_status ON customer(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_plan ON customer(plan)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_industry ON customer(industry)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_created_at ON customer(created_at)")

    # 2) Add customer_id FK to core business tables
    for table in _TENANT_TABLES:
        op.execute(f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS customer_id INTEGER
            REFERENCES customer(id) ON DELETE SET NULL
        """)
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_customer_id "
            f"ON {table}(customer_id)"
        )


def downgrade() -> None:
    for table in _TENANT_TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_customer_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS customer_id")
    # 不 drop customer 表，避免误删客户数据
