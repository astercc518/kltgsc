"""keyword_monitor customer-scoped rules (S2.2)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-05-21

Adds `keywordmonitor.customer_id` so external customers (via /portal/monitors)
can author their own monitor rules. When set, the listener only fires the
rule on TG accounts whose `account.customer_id` matches. NULL keeps the
existing semantics (admin/platform-wide rule or sales-owned via
created_by_sales_user_id).

`customer_id` is conceptually mutually exclusive with
`created_by_sales_user_id` — a rule is either customer-owned or sales-owned,
not both. The listener evaluates each filter independently so the model
itself doesn't enforce the XOR.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('keywordmonitor')}
    if 'customer_id' not in cols:
        op.add_column(
            'keywordmonitor',
            sa.Column('customer_id', sa.Integer(), nullable=True),
        )
        op.create_index(
            'ix_keywordmonitor_customer_id',
            'keywordmonitor',
            ['customer_id'],
        )
        # FK to customer.id — best-effort, SQLite skips it gracefully.
        try:
            op.create_foreign_key(
                'fk_keywordmonitor_customer_id',
                'keywordmonitor', 'customer',
                ['customer_id'], ['id'],
            )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('keywordmonitor')}
    if 'customer_id' in cols:
        try:
            op.drop_constraint('fk_keywordmonitor_customer_id',
                               'keywordmonitor', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_index('ix_keywordmonitor_customer_id',
                          table_name='keywordmonitor')
        except Exception:
            pass
        op.drop_column('keywordmonitor', 'customer_id')
