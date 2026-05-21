"""add sales_wallet + invoice.sales_owner_* (Epic C2)

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-05-21

- sales_wallet: composite-PK personal wallets for sub-user sales
  (owner_type='customer_sales', owner_id=customer_user.id) and platform
  sales (owner_type='platform_sales', owner_id=user.id).
- sales_wallet_transaction: txn log with same structure as
  wallet_transaction but tagged by owner_type/owner_id, also linkable to
  Lead.id (for lead-view charges in Epic D).
- invoice.sales_owner_type / sales_owner_id: nullable cols on the
  existing Invoice table so a topup invoice can be routed to a sales
  wallet instead of the customer wallet when paid. For customer_sales
  the invoice still carries the parent customer_id (the customer pays
  for the sales seat's viewing budget); platform_sales topups don't go
  through Invoice and are credited via admin tools.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'sales_wallet' not in inspector.get_table_names():
        op.create_table(
            'sales_wallet',
            sa.Column('owner_type', sa.String(length=20), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('balance_cents', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_topup_cents', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_spent_cents', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('owner_type', 'owner_id'),
        )
        op.create_index('ix_sales_wallet_owner_id', 'sales_wallet', ['owner_id'])

    if 'sales_wallet_transaction' not in inspector.get_table_names():
        op.create_table(
            'sales_wallet_transaction',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('owner_type', sa.String(length=20), nullable=False, index=True),
            sa.Column('owner_id', sa.Integer(), nullable=False, index=True),
            sa.Column('type', sa.String(length=20), nullable=False, index=True),
            sa.Column('amount_cents', sa.Integer(), nullable=False),
            sa.Column('balance_after_cents', sa.Integer(), nullable=False),
            sa.Column('description', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoice.id'), nullable=True),
            sa.Column('lead_id', sa.Integer(), sa.ForeignKey('lead.id'), nullable=True),
            sa.Column('idempotency_key', sa.String(length=120), nullable=False, unique=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.func.now(), index=True),
        )

    inv_cols = {c['name'] for c in inspector.get_columns('invoice')}
    if 'sales_owner_type' not in inv_cols:
        op.add_column('invoice', sa.Column('sales_owner_type', sa.String(length=20), nullable=True))
    if 'sales_owner_id' not in inv_cols:
        op.add_column('invoice', sa.Column('sales_owner_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    inv_cols = {c['name'] for c in inspector.get_columns('invoice')}
    if 'sales_owner_id' in inv_cols:
        op.drop_column('invoice', 'sales_owner_id')
    if 'sales_owner_type' in inv_cols:
        op.drop_column('invoice', 'sales_owner_type')

    if 'sales_wallet_transaction' in inspector.get_table_names():
        op.drop_table('sales_wallet_transaction')
    if 'sales_wallet' in inspector.get_table_names():
        try:
            op.drop_index('ix_sales_wallet_owner_id', table_name='sales_wallet')
        except Exception:
            pass
        op.drop_table('sales_wallet')
