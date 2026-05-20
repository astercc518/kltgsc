"""Epic 3: add allocation/customization fields to account + industry to source_group

Revision ID: a3b4c5d6e7f8
Revises: f2b3c4d5e6a7
Create Date: 2026-05-18

Adds:
- account.assigned_at + customized_{username,first_name,last_name,bio} + replaced_account_id
- sourcegroup.industry + assigned_at
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2b3c4d5e6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Account
    for col, ddl in [
        ("assigned_at", "TIMESTAMP"),
        ("customized_username", "VARCHAR(64)"),
        ("customized_first_name", "VARCHAR(64)"),
        ("customized_last_name", "VARCHAR(64)"),
        ("customized_bio", "VARCHAR(280)"),
        ("replaced_account_id", "INTEGER REFERENCES account(id) ON DELETE SET NULL"),
    ]:
        op.execute(
            f"ALTER TABLE account ADD COLUMN IF NOT EXISTS {col} {ddl}"
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_account_assigned_at ON account(assigned_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_account_replaced_account_id ON account(replaced_account_id)")

    # SourceGroup
    op.execute("ALTER TABLE sourcegroup ADD COLUMN IF NOT EXISTS industry VARCHAR(40)")
    op.execute("ALTER TABLE sourcegroup ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sourcegroup_industry ON sourcegroup(industry)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sourcegroup_assigned_at ON sourcegroup(assigned_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sourcegroup_assigned_at")
    op.execute("DROP INDEX IF EXISTS ix_sourcegroup_industry")
    op.execute("ALTER TABLE sourcegroup DROP COLUMN IF EXISTS assigned_at")
    op.execute("ALTER TABLE sourcegroup DROP COLUMN IF EXISTS industry")
    op.execute("DROP INDEX IF EXISTS ix_account_replaced_account_id")
    op.execute("DROP INDEX IF EXISTS ix_account_assigned_at")
    for col in ["replaced_account_id", "customized_bio", "customized_last_name",
                "customized_first_name", "customized_username", "assigned_at"]:
        op.execute(f"ALTER TABLE account DROP COLUMN IF EXISTS {col}")
