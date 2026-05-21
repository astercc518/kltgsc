"""sales-owned accounts + monitor rules (Phase G)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-21

Adds the ownership link letting an individual salesperson (platform or
customer) manage a subset of TG accounts and author their own keyword
monitor rules. The listener uses the join to scope which rules fire on
which accounts.

- account.assigned_to_sales_user_id (int FK-ish, nullable)
- account.assigned_to_sales_kind ('platform' | 'customer', nullable)
- keywordmonitor.created_by_sales_user_id (int, nullable)
- keywordmonitor.created_by_sales_kind ('platform' | 'customer', nullable)

No FK constraints — id space collides between User and CustomerUser, so
we keep the (id, kind) pair as a tagged ref instead of a hard FK.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    acc_cols = {c['name'] for c in inspector.get_columns('account')}
    if 'assigned_to_sales_user_id' not in acc_cols:
        op.add_column('account', sa.Column('assigned_to_sales_user_id', sa.Integer(), nullable=True))
        op.create_index('ix_account_assigned_to_sales_user_id', 'account',
                        ['assigned_to_sales_user_id'])
    if 'assigned_to_sales_kind' not in acc_cols:
        op.add_column('account', sa.Column('assigned_to_sales_kind', sa.String(length=20), nullable=True))

    mon_cols = {c['name'] for c in inspector.get_columns('keywordmonitor')}
    if 'created_by_sales_user_id' not in mon_cols:
        op.add_column('keywordmonitor', sa.Column('created_by_sales_user_id', sa.Integer(), nullable=True))
        op.create_index('ix_keywordmonitor_created_by_sales_user_id', 'keywordmonitor',
                        ['created_by_sales_user_id'])
    if 'created_by_sales_kind' not in mon_cols:
        op.add_column('keywordmonitor', sa.Column('created_by_sales_kind', sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    mon_cols = {c['name'] for c in inspector.get_columns('keywordmonitor')}
    if 'created_by_sales_kind' in mon_cols:
        op.drop_column('keywordmonitor', 'created_by_sales_kind')
    if 'created_by_sales_user_id' in mon_cols:
        try:
            op.drop_index('ix_keywordmonitor_created_by_sales_user_id', table_name='keywordmonitor')
        except Exception:
            pass
        op.drop_column('keywordmonitor', 'created_by_sales_user_id')

    acc_cols = {c['name'] for c in inspector.get_columns('account')}
    if 'assigned_to_sales_kind' in acc_cols:
        op.drop_column('account', 'assigned_to_sales_kind')
    if 'assigned_to_sales_user_id' in acc_cols:
        try:
            op.drop_index('ix_account_assigned_to_sales_user_id', table_name='account')
        except Exception:
            pass
        op.drop_column('account', 'assigned_to_sales_user_id')
