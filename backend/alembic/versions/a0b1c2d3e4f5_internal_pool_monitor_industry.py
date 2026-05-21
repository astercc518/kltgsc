"""add customer.is_internal_pool + keywordmonitor.industry (Phase F1)

Revision ID: a0b1c2d3e4f5
Revises: 9c0d1e2f3a4b
Create Date: 2026-05-21

Two columns enable the internal-sales-pool playbook:

- customer.is_internal_pool: marks a Customer row as the platform's own
  lead pool container (no subscription, no wallet billing). Used by
  sales_leads._scope_to_sales to filter platform_sales visibility.
- keywordmonitor.industry: when a monitor rule hits, the auto-created
  Lead inherits this industry so the sales workbench can group by
  business vertical.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = '9c0d1e2f3a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cust_cols = {c['name'] for c in inspector.get_columns('customer')}
    if 'is_internal_pool' not in cust_cols:
        op.add_column(
            'customer',
            sa.Column('is_internal_pool', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
        )
        op.create_index('ix_customer_is_internal_pool', 'customer', ['is_internal_pool'])

    mon_cols = {c['name'] for c in inspector.get_columns('keywordmonitor')}
    if 'industry' not in mon_cols:
        op.add_column(
            'keywordmonitor',
            sa.Column('industry', sa.String(length=50), nullable=True),
        )
        op.create_index('ix_keywordmonitor_industry', 'keywordmonitor', ['industry'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    mon_cols = {c['name'] for c in inspector.get_columns('keywordmonitor')}
    if 'industry' in mon_cols:
        try:
            op.drop_index('ix_keywordmonitor_industry', table_name='keywordmonitor')
        except Exception:
            pass
        op.drop_column('keywordmonitor', 'industry')

    cust_cols = {c['name'] for c in inspector.get_columns('customer')}
    if 'is_internal_pool' in cust_cols:
        try:
            op.drop_index('ix_customer_is_internal_pool', table_name='customer')
        except Exception:
            pass
        op.drop_column('customer', 'is_internal_pool')
