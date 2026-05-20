"""add customer_wallet.low_balance_notified_at (W5)

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-05-20

Adds a single nullable timestamp column so the low-balance watcher can avoid
re-notifying the same customer every beat tick. Cleared when next topup
brings balance back above the threshold.

参考 docs/planning/bulk_send_spec.md §2.3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('customer_wallet')}
    if 'low_balance_notified_at' not in cols:
        op.add_column(
            'customer_wallet',
            sa.Column('low_balance_notified_at', sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('customer_wallet')}
    if 'low_balance_notified_at' in cols:
        op.drop_column('customer_wallet', 'low_balance_notified_at')
